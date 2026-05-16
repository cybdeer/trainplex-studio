"""TrainPlex payments API — Phase 1 Step 6.4 + 4.2-5.

URLs
----
    GET  /api/v1/payments/wallet
        → trainer's own wallet (balance, held balance, this-month
        earnings, recent 30 transactions). Trainer-only.

    GET  /api/v1/payments/payout-queue
        → admin-only list of pending / failed PayoutQueue entries
        (admin retry surface).

    POST /api/v1/payments/payout-queue/<id>/retry
        → admin-only manual retry of a stuck / failed payout.

    GET  /api/v1/admin/payment-status
        → admin-only payment status table (per-task hold / released /
        disputed / refunded view, for Step 4.2-5).

All endpoints role-gated via ``users.decorators.require_role``. The
trainer wallet endpoint is implicitly self-only (the response is always
``request.user``'s rows; there is no `?user_id=` query — a misrouted
admin lookup against another trainer's wallet returns 403 not 200).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from decimal import Decimal
from math import ceil
from typing import Any, Dict

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import PaymentHold, PayoutQueue, WalletTransaction
from payments.services import razorpay_handler  # rollback path; do not remove
from payments.services import payout_provider  # Wave-19 W2-PAYOUT — active provider shim
from payments.services import shivgateway_handler  # active payout rail
from payments.services import wallet as wallet_service
from users.decorators import require_role

logger = logging.getLogger(__name__)


_PAGE_SIZE_DEFAULT = 50
_PAGE_SIZE_MAX = 200
_HOLD_STATUS_VALUES = {'held', 'released', 'disputed', 'refunded'}


# ---------------------------------------------------------------------------
# small helpers — kept private
# ---------------------------------------------------------------------------


def _coerce_positive_int(value: Any, default: int, hard_max: 'int | None' = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    if hard_max is not None and parsed > hard_max:
        return hard_max
    return parsed


def _iso(value) -> 'str | None':
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat().replace('+00:00', 'Z')
    return str(value)


def _decimal_to_str(value: Decimal) -> str:
    """Stable decimal serialisation. Frontend formats with INR symbol."""
    if value is None:
        return '0.00'
    return f'{Decimal(value):.2f}'


def _serialize_transaction(txn: WalletTransaction) -> Dict[str, Any]:
    return {
        'id': txn.id,
        'txn_type': txn.txn_type,
        'amount_inr': _decimal_to_str(txn.amount_inr),
        'balance_after_inr': _decimal_to_str(txn.balance_after_inr),
        'description': txn.description or '',
        'related_task_id': txn.related_task_id,
        'related_payout_id': txn.related_payout_id,
        'created_at': _iso(txn.created_at),
    }


def _serialize_payout(p: PayoutQueue) -> Dict[str, Any]:
    return {
        'id': p.id,
        'trainer_id': p.trainer_id,
        'amount_inr': _decimal_to_str(p.amount_inr),
        'status': p.status,
        'razorpay_payout_id': p.razorpay_payout_id or '',
        'retry_count': p.retry_count,
        'last_error': (p.last_error or '')[:500],
        'created_at': _iso(p.created_at),
        'sent_at': _iso(p.sent_at),
    }


def _serialize_hold(h: PaymentHold) -> Dict[str, Any]:
    return {
        'id': h.id,
        'task_id': h.task_id,
        'trainer_id': h.trainer_id,
        'amount_inr': _decimal_to_str(h.amount_inr),
        'status': h.status,
        'held_at': _iso(h.held_at),
        'released_at': _iso(h.released_at),
        'consensus_result_id': h.consensus_result_id,
        'payout_queue_id': h.payout_queue_id,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/payments/wallet  (trainer-only, self)
# ---------------------------------------------------------------------------


class TrainerWalletAPI(APIView):
    """Trainer wallet — balance, held, this-month, recent transactions.

    Trainer-only. The response is always the request.user's own rows;
    there is no `?user_id=` query parameter so an admin cannot pull
    another trainer's wallet via this surface (admins use
    /admin/payment-status for that).
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Trainer'],
        summary='Trainer wallet — balance + held + recent txns',
    )
    @require_role(['trainer'])
    def get(self, request, *args, **kwargs):
        user = request.user
        limit = _coerce_positive_int(
            request.query_params.get('limit'),
            default=30,
            hard_max=100,
        )
        balance = wallet_service.get_balance(user)
        held = wallet_service.get_held_balance(user)
        month_earnings = wallet_service.get_month_earnings(user)
        txns = wallet_service.get_recent_transactions(user, limit=limit)

        return Response(
            {
                'balance_inr': _decimal_to_str(balance),
                'held_inr': _decimal_to_str(held),
                'this_month_inr': _decimal_to_str(month_earnings),
                'transactions': [_serialize_transaction(t) for t in txns],
                'transaction_limit': limit,
            },
            status=200,
        )


# ---------------------------------------------------------------------------
# GET /api/v1/payments/payout-queue  (admin-only)
# ---------------------------------------------------------------------------


class AdminPayoutQueueAPI(APIView):
    """Admin-only list of PayoutQueue entries.

    Query params
    ------------
    * ``status`` — pending / processing / sent / failed / all. Default: pending.
    * ``trainer_id`` — filter by single trainer (audit).
    * ``page`` / ``page_size`` — pagination (default 50, cap 200).
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Admin — list payout queue',
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        page = _coerce_positive_int(request.query_params.get('page'), default=1)
        page_size = _coerce_positive_int(
            request.query_params.get('page_size'),
            default=_PAGE_SIZE_DEFAULT,
            hard_max=_PAGE_SIZE_MAX,
        )

        status_q = (request.query_params.get('status') or '').strip().lower()
        qs = PayoutQueue.objects.all()
        if status_q == 'all':
            pass
        elif status_q in {'pending', 'processing', 'sent', 'failed'}:
            qs = qs.filter(status=status_q)
        else:
            # Default — show actionable queue (pending + processing + failed).
            qs = qs.filter(status__in=[
                PayoutQueue.STATUS_PENDING,
                PayoutQueue.STATUS_PROCESSING,
                PayoutQueue.STATUS_FAILED,
            ])

        trainer_id_raw = request.query_params.get('trainer_id')
        if trainer_id_raw:
            try:
                qs = qs.filter(trainer_id=int(trainer_id_raw))
            except (TypeError, ValueError):
                return Response({'error': 'trainer_id must be an integer'}, status=400)

        qs = qs.order_by('-created_at')
        total = qs.count()
        total_pages = ceil(total / page_size) if total else 0
        offset = (page - 1) * page_size
        rows = list(qs[offset: offset + page_size])

        return Response(
            {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': total_pages,
                'results': [_serialize_payout(p) for p in rows],
            },
            status=200,
        )


# ---------------------------------------------------------------------------
# POST /api/v1/payments/payout-queue/<id>/retry  (admin-only)
# ---------------------------------------------------------------------------


class AdminPayoutRetryAPI(APIView):
    """Admin manual retry of a failed / stuck payout."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Admin — manual payout retry',
    )
    @require_role(['admin'])
    def post(self, request, payout_id: int, *args, **kwargs):
        # Wave-19 W2-PAYOUT: route via provider shim so retries hit
        # whichever provider is currently active (default: ShivGateway).
        entry = payout_provider.retry_payout(payout_id)
        if entry is None:
            return Response({'error': 'payout not found'}, status=404)
        return Response({'ok': True, 'payout': _serialize_payout(entry)}, status=200)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/payment-status  (admin-only, Step 4.2-5)
# ---------------------------------------------------------------------------


class AdminPaymentStatusAPI(APIView):
    """Admin — per-task payment status table.

    Query params
    ------------
    * ``status`` — held / released / disputed / refunded / all (default all).
    * ``trainer_id`` — filter by single trainer.
    * ``task_id`` — single-task lookup.
    * ``page`` / ``page_size`` — pagination.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Admin — payment status table',
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        page = _coerce_positive_int(request.query_params.get('page'), default=1)
        page_size = _coerce_positive_int(
            request.query_params.get('page_size'),
            default=_PAGE_SIZE_DEFAULT,
            hard_max=_PAGE_SIZE_MAX,
        )

        qs = PaymentHold.objects.all()

        status_q = (request.query_params.get('status') or '').strip().lower()
        if status_q and status_q != 'all':
            if status_q not in _HOLD_STATUS_VALUES:
                return Response(
                    {'error': f'status must be one of {sorted(_HOLD_STATUS_VALUES)}'},
                    status=400,
                )
            qs = qs.filter(status=status_q)

        trainer_id_raw = request.query_params.get('trainer_id')
        if trainer_id_raw:
            try:
                qs = qs.filter(trainer_id=int(trainer_id_raw))
            except (TypeError, ValueError):
                return Response({'error': 'trainer_id must be an integer'}, status=400)

        task_id_raw = request.query_params.get('task_id')
        if task_id_raw:
            try:
                qs = qs.filter(task_id=int(task_id_raw))
            except (TypeError, ValueError):
                return Response({'error': 'task_id must be an integer'}, status=400)

        qs = qs.order_by('-held_at')
        total = qs.count()
        total_pages = ceil(total / page_size) if total else 0
        offset = (page - 1) * page_size
        rows = list(qs[offset: offset + page_size])

        # Stats summary for the dashboard widget header — counts per status
        # across the unfiltered table (admin spot-check).
        # We do these on the unfiltered queryset to keep the summary stable
        # regardless of the active filter.
        summary_qs = PaymentHold.objects.all()
        summary = {
            'held': summary_qs.filter(status=PaymentHold.STATUS_HELD).count(),
            'released': summary_qs.filter(status=PaymentHold.STATUS_RELEASED).count(),
            'disputed': summary_qs.filter(status=PaymentHold.STATUS_DISPUTED).count(),
            'refunded': summary_qs.filter(status=PaymentHold.STATUS_REFUNDED).count(),
        }

        return Response(
            {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': total_pages,
                'summary': summary,
                'results': [_serialize_hold(h) for h in rows],
            },
            status=200,
        )


# ---------------------------------------------------------------------------
# POST /api/v1/payments/razorpay-webhook  (no-auth, signed)
# ---------------------------------------------------------------------------


class RazorpayWebhookAPI(APIView):
    """Webhook receiver for Razorpay X payout events.

    Wave-19 W2-MOCK-REAL. Razorpay signs every webhook with HMAC-SHA256
    over the raw body using the shared secret in ``RAZORPAY_WEBHOOK_SECRET``.
    We verify in constant time, refuse 400 on any mismatch, then dispatch
    to :func:`razorpay_handler.process_webhook_event` which translates
    ``payout.processed`` / ``payout.reversed`` / ``payout.failed`` into the
    matching ``PayoutQueue`` row update.

    Auth model: ``permission_classes = (AllowAny,)`` because Razorpay is a
    public-internet POST source. The signature header IS the auth. We
    intentionally never log the raw body to avoid leaking PII; only the
    parsed event type + matched queue id surface in logs.
    """

    permission_classes = (AllowAny,)
    authentication_classes: tuple = ()

    @extend_schema(
        tags=['Payments'],
        summary='Razorpay X payout webhook receiver',
        description=(
            'Signed by Razorpay via X-Razorpay-Signature. Verified with '
            'HMAC-SHA256 over the raw body using the env-only '
            'RAZORPAY_WEBHOOK_SECRET. 400 on invalid signature, 200 on '
            'verified event with idempotent processing.'
        ),
    )
    def post(self, request, *args, **kwargs):
        secret = (os.getenv('RAZORPAY_WEBHOOK_SECRET') or '').strip()
        signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '') or ''
        # request.body is already raw bytes per DRF semantics.
        raw_body = request.body.decode('utf-8') if request.body else ''

        if not secret:
            # Misconfigured — refuse rather than silently 200. The founder
            # sets the secret once Razorpay returns the value from the
            # Razorpay X webhook setup screen.
            logger.warning(
                'payments.razorpay.webhook misconfig: RAZORPAY_WEBHOOK_SECRET empty'
            )
            return Response(
                {'error': 'webhook secret not configured'}, status=503,
            )

        if not razorpay_handler.verify_webhook_signature(
            body=raw_body, signature=signature, secret=secret,
        ):
            logger.warning('payments.razorpay.webhook invalid signature')
            return Response({'error': 'invalid signature'}, status=400)

        try:
            event = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            return Response({'error': 'invalid json'}, status=400)

        result = razorpay_handler.process_webhook_event(event)
        logger.info('payments.razorpay.webhook processed result=%s', result)
        return Response({'ok': True, 'result': result}, status=200)


# ---------------------------------------------------------------------------
# POST /api/v1/payments/shivgateway-webhook  (no-auth, signed) — Wave-19 W2-PAYOUT
# ---------------------------------------------------------------------------


class ShivGatewayWebhookAPI(APIView):
    """Webhook receiver for ShivGateway payout events.

    Drop-in counterpart of :class:`RazorpayWebhookAPI`. Signature scheme is
    HMAC-SHA256 over the raw body using ``SHIVGATEWAY_WEBHOOK_SECRET``
    (falls back to ``SHIVGATEWAY_API_SECRET`` if the dedicated webhook
    secret env var is unset — placeholder until founder confirms scheme).

    Header convention used here: ``X-ShivGateway-Signature``. If the live
    contract turns out to use a different header, swap the META key below
    and the handler matches transparently.
    """

    permission_classes = (AllowAny,)
    authentication_classes: tuple = ()

    @extend_schema(
        tags=['Payments'],
        summary='ShivGateway payout webhook receiver',
        description=(
            'Signed by ShivGateway via X-ShivGateway-Signature. Verified '
            'with HMAC-SHA256 over the raw body using '
            'SHIVGATEWAY_WEBHOOK_SECRET (or SHIVGATEWAY_API_SECRET '
            'fallback). 400 on invalid signature, 200 on verified event.'
        ),
    )
    def post(self, request, *args, **kwargs):
        secret = (
            os.getenv('SHIVGATEWAY_WEBHOOK_SECRET')
            or os.getenv('SHIVGATEWAY_API_SECRET')
            or ''
        ).strip()
        signature = (
            request.META.get('HTTP_X_SHIVGATEWAY_SIGNATURE')
            or request.META.get('HTTP_X_SHIV_SIGNATURE')
            or ''
        )
        raw_body = request.body.decode('utf-8') if request.body else ''

        if not secret:
            logger.warning(
                'payments.shivgateway.webhook misconfig: webhook secret empty'
            )
            return Response(
                {'error': 'webhook secret not configured'}, status=503,
            )

        if not shivgateway_handler.verify_webhook_signature(
            body=raw_body, signature=signature, secret=secret,
        ):
            logger.warning('payments.shivgateway.webhook invalid signature')
            return Response({'error': 'invalid signature'}, status=400)

        try:
            event = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            return Response({'error': 'invalid json'}, status=400)

        result = shivgateway_handler.process_webhook_event(event)
        logger.info('payments.shivgateway.webhook processed result=%s', result)
        return Response({'ok': True, 'result': result}, status=200)
