"""TrainPlex payments — ShivGateway payout handler (Wave-19 W2-PAYOUT).

Drop-in replacement for ``razorpay_handler``. Same public surface so the
router + cron flush + admin retry + webhook all keep working without
changes downstream of ``payments.services.payout_router``.

Founder decision (2026-05-16)
-----------------------------
Razorpay X is dropped. ShivGateway is the new payout rail. The Razorpay
handler is kept in-tree as a rollback-only artefact (see
``razorpay_handler.py`` deprecation header). The router picks the
provider via ``TRAINPLEX_PAYOUT_PROVIDER`` (default: ``shivgateway``).

Safety gates
------------
* ``TRAINPLEX_PAYOUT_DRY_RUN`` defaults to ``true`` — no real money moves
  until the founder flips it. With dry-run on (or creds missing), we
  emit a deterministic ``shiv-dryrun-<hex>`` synthetic id and run the
  full lifecycle (mark_sent -> wallet debit row) so the rest of the
  pipeline stays exercised.
* The ShivGateway HTTP contract used below (endpoints, auth header,
  webhook signature scheme) is a **placeholder** until the founder
  confirms the actual integration spec. Switching to the real contract
  is a single-file edit; the public function signatures here do NOT
  change.
* No founder personal mobile in any payload — payouts identify the
  trainer via the queue row's reference id, never via free-text
  contact details. (MEMORY.md -> feedback_no_founder_personal_number.md)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import uuid
from typing import Any, Dict, Optional

import requests
from django.db import transaction
from django.utils import timezone

from payments.models import PayoutQueue, WalletTransaction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ShivGateway HTTP config — placeholder values until founder confirms.
# ---------------------------------------------------------------------------

SHIVGATEWAY_DEFAULT_BASE_URL = 'https://api.shivgateway.in/v1'
SHIVGATEWAY_DEFAULT_TIMEOUT_SECONDS = 30


def _dry_run_default() -> bool:
    raw = os.getenv('TRAINPLEX_PAYOUT_DRY_RUN', 'true').strip().lower()
    return raw not in ('false', '0', 'no', 'off')


def _credentials() -> Dict[str, str]:
    return {
        'key': (os.getenv('SHIVGATEWAY_API_KEY') or '').strip(),
        'secret': (os.getenv('SHIVGATEWAY_API_SECRET') or '').strip(),
        'webhook_secret': (
            os.getenv('SHIVGATEWAY_WEBHOOK_SECRET')
            or os.getenv('SHIVGATEWAY_API_SECRET')
            or ''
        ).strip(),
        'base_url': (
            os.getenv('SHIVGATEWAY_API_URL') or SHIVGATEWAY_DEFAULT_BASE_URL
        ).rstrip('/'),
    }


def verify_webhook_signature(*, body: str, signature: str, secret: str) -> bool:
    """HMAC-SHA256 verify for ShivGateway webhook payload.

    Placeholder scheme: ``hmac_sha256(secret, raw_body).hexdigest()``.
    Same algorithm Razorpay uses and the most common pattern for Indian
    payout gateways. If ShivGateway publishes a different scheme this is
    the only function to flip.

    Constant-time compare via ``hmac.compare_digest`` to avoid timing
    leaks. Returns ``True`` on a valid signature; ``False`` otherwise.
    """
    if not body or not signature or not secret:
        return False
    body_bytes = body.encode('utf-8') if isinstance(body, str) else body
    expected = hmac.new(
        key=secret.encode('utf-8'),
        msg=body_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


# ---------------------------------------------------------------------------
# Public API — matches razorpay_handler.send_payout signature exactly so
# payout_router can call either provider with the same args.
# ---------------------------------------------------------------------------


def send_payout(
    payout_queue_entry: PayoutQueue,
    *,
    force_mock_failure: bool = False,
    dry_run: Optional[bool] = None,
) -> PayoutQueue:
    """Attempt a payout via ShivGateway. Returns the updated PayoutQueue row.

    Lifecycle matches the Razorpay handler:
        1. Row-lock and flip pending -> processing.
        2. Dry-run or no-creds -> synthesise a ``shiv-dryrun-<hex>`` id
           and run mark_sent (wallet debit lands).
        3. Real call -> ``POST {base}/payouts`` with the trainer-safe
           payload, then mark_sent on 2xx or mark_failed on error.

    The ``razorpay_payout_id`` column on PayoutQueue is reused to store
    whatever id the active provider returns — renaming that column would
    require a migration AND touch every serializer; we keep it as the
    provider-agnostic ``external payout id`` slot. Logs disambiguate
    with ``provider=shivgateway``.
    """
    if payout_queue_entry.status not in (
        PayoutQueue.STATUS_PENDING,
        PayoutQueue.STATUS_PROCESSING,
    ):
        logger.warning(
            'payments.shivgateway.send_payout SKIP queue_id=%s status=%s '
            '— not in sendable state',
            payout_queue_entry.id, payout_queue_entry.status,
        )
        return payout_queue_entry

    # Row-lock-and-flip so two workers don't race a double-send.
    with transaction.atomic():
        locked = PayoutQueue.objects.select_for_update().get(id=payout_queue_entry.id)
        if locked.status == PayoutQueue.STATUS_SENT:
            return locked
        locked.status = PayoutQueue.STATUS_PROCESSING
        locked.save(update_fields=['status'])

    if force_mock_failure:
        return mark_failed(locked.id, 'mock failure (test hook)')

    if dry_run is None:
        dry_run = _dry_run_default()
    creds = _credentials()
    have_creds = bool(creds['key'] and creds['secret'])

    if dry_run or not have_creds:
        synth_id = f'shiv-dryrun-{uuid.uuid4().hex[:12]}'
        logger.info(
            'payments.shivgateway.send_payout dry-run queue_id=%s id=%s '
            'amount=%s (TRAINPLEX_PAYOUT_DRY_RUN=%s, creds_present=%s)',
            locked.id, synth_id, locked.amount_inr, dry_run, have_creds,
        )
        return mark_sent(locked.id, synth_id)

    # Real ShivGateway payout — placeholder contract (founder to confirm).
    amount_paise = int(round(float(locked.amount_inr) * 100))
    reference_id = f'trainplex-pq-{locked.id}'
    body = {
        'amount_paise': amount_paise,
        'currency': 'INR',
        'reference_id': reference_id,
        'narration': f'TrainPlex task payout #{locked.id}'[:80],
        'mode': 'IMPS',
    }
    headers = {
        'Authorization': f"Bearer {creds['key']}",
        'X-API-Secret': creds['secret'],
        'X-Idempotency-Key': reference_id,
        'Content-Type': 'application/json',
    }
    url = f"{creds['base_url']}/payouts"
    try:
        resp = requests.post(
            url,
            json=body,
            headers=headers,
            timeout=SHIVGATEWAY_DEFAULT_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json() if resp.content else {}
    except Exception as exc:
        return mark_failed(locked.id, f'shivgateway error: {exc!s}')

    real_id = (
        payload.get('id')
        or payload.get('payout_id')
        or f'shivgateway-{uuid.uuid4().hex[:12]}'
    )
    logger.info(
        'payments.shivgateway.send_payout live queue_id=%s shiv_id=%s',
        locked.id, real_id,
    )
    return mark_sent(locked.id, real_id)


def process_webhook_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Update the matching PayoutQueue row from a verified webhook event.

    Placeholder ShivGateway event shape (founder to confirm):
        {
          "event": "payout.processed" | "payout.failed" | "payout.reversed",
          "payload": {"payout": {"entity": {"id": ..., "reference_id": ...}}}
        }

    The matcher keys off ``reference_id`` (which we set to
    ``trainplex-pq-<id>`` on outbound) so the lookup survives even if
    ShivGateway rotates the external id. Idempotent — second fire for
    an already-resolved row is a no-op.
    """
    event_type = (event or {}).get('event') or ''
    payout_entity = (
        ((event or {}).get('payload') or {}).get('payout') or {}
    ).get('entity') or {}
    reference_id = payout_entity.get('reference_id') or ''
    external_id = payout_entity.get('id') or ''
    if not reference_id.startswith('trainplex-pq-'):
        return {'matched': False, 'reason': 'reference_id missing or unknown'}
    try:
        pq_id = int(reference_id.split('-')[-1])
    except (TypeError, ValueError):
        return {'matched': False, 'reason': 'reference_id not parseable'}

    try:
        entry = PayoutQueue.objects.get(id=pq_id)
    except PayoutQueue.DoesNotExist:
        return {'matched': False, 'reason': f'payout_queue {pq_id} not found'}

    status_map = {
        'payout.processed': PayoutQueue.STATUS_SENT,
        'payout.reversed': PayoutQueue.STATUS_FAILED,
        'payout.failed': PayoutQueue.STATUS_FAILED,
    }
    new_status = status_map.get(event_type)
    if new_status is None:
        return {'matched': True, 'noop': True, 'event': event_type}

    if new_status == PayoutQueue.STATUS_SENT:
        mark_sent(entry.id, external_id or entry.razorpay_payout_id or f'shivgateway-{pq_id}')
    else:
        mark_failed(entry.id, f'webhook {event_type}')

    return {'matched': True, 'event': event_type, 'pq_id': pq_id, 'provider': 'shivgateway'}


def mark_sent(payout_id: int, external_payout_id: str) -> PayoutQueue:
    """Finalise a successful payout. Writes the wallet debit row.

    Idempotent — second call for the same row is a no-op. The
    ``razorpay_payout_id`` column stores the ShivGateway id (legacy
    column name, provider-agnostic semantics — see send_payout docstring).
    """
    with transaction.atomic():
        entry = PayoutQueue.objects.select_for_update().get(id=payout_id)
        if entry.status == PayoutQueue.STATUS_SENT:
            return entry

        entry.status = PayoutQueue.STATUS_SENT
        entry.razorpay_payout_id = external_payout_id
        entry.sent_at = timezone.now()
        entry.last_error = ''
        entry.save(
            update_fields=['status', 'razorpay_payout_id', 'sent_at', 'last_error'],
        )

        already_written = WalletTransaction.objects.filter(
            user=entry.trainer,
            txn_type=WalletTransaction.TYPE_PAYOUT,
            related_payout_id=entry.id,
        ).exists()
        if not already_written:
            from payments.services.wallet import get_balance  # local — avoid cycle
            current = get_balance(entry.trainer)
            new_balance = current - entry.amount_inr
            WalletTransaction.objects.create(
                user=entry.trainer,
                txn_type=WalletTransaction.TYPE_PAYOUT,
                amount_inr=entry.amount_inr,
                balance_after_inr=new_balance,
                description=f'Task payout #{entry.id}',
                related_payout_id=entry.id,
            )

    logger.info(
        'payments.shivgateway.mark_sent queue_id=%s shiv_id=%s amount=%s',
        entry.id, external_payout_id, entry.amount_inr,
    )
    return entry


def mark_failed(payout_id: int, error: str) -> PayoutQueue:
    """Record a failure + bump retry_count. Parks at ``failed`` after MAX_RETRIES.

    Identical retry semantics to the Razorpay handler so the cron flush
    and admin retry surface keep working without changes.
    """
    with transaction.atomic():
        entry = PayoutQueue.objects.select_for_update().get(id=payout_id)
        entry.last_error = (error or '')[:1000]
        entry.retry_count = (entry.retry_count or 0) + 1
        if entry.retry_count >= PayoutQueue.MAX_RETRIES:
            entry.status = PayoutQueue.STATUS_FAILED
        else:
            entry.status = PayoutQueue.STATUS_PENDING
        entry.save(update_fields=['last_error', 'retry_count', 'status'])

    logger.warning(
        'payments.shivgateway.mark_failed queue_id=%s retry=%s status=%s err=%s',
        entry.id, entry.retry_count, entry.status, error,
    )
    return entry


def retry_payout(payout_id: int) -> Optional[PayoutQueue]:
    """Manual admin-triggered retry. Same semantics as razorpay_handler."""
    try:
        entry = PayoutQueue.objects.get(id=payout_id)
    except PayoutQueue.DoesNotExist:
        logger.warning('payments.shivgateway.retry_payout payout_id=%s not found', payout_id)
        return None

    if entry.status == PayoutQueue.STATUS_SENT:
        return entry

    with transaction.atomic():
        locked = PayoutQueue.objects.select_for_update().get(id=entry.id)
        locked.status = PayoutQueue.STATUS_PENDING
        locked.last_error = ''
        locked.save(update_fields=['status', 'last_error'])

    return send_payout(locked)
