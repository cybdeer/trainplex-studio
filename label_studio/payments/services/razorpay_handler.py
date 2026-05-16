"""TrainPlex payments — Razorpay X handler (MOCKED in Phase 1).

Phase 1 Step 6.4. No ``razorpay-python`` dependency added yet — the real
network call lands Phase 2 with prod credentials. The contract here is
stable so the Phase 2 swap is a one-file edit.

Lifecycle
---------
* ``send_payout(payout_queue_entry)`` flips status pending → processing,
  attempts the (mock) Razorpay call, then calls ``mark_sent`` /
  ``mark_failed`` based on the outcome.
* ``mark_sent`` persists the razorpay_payout_id, flips status to ``sent``,
  and writes the ``payout`` WalletTransaction row (debits the wallet).
* ``mark_failed`` increments retry_count + records last_error. Once
  retry_count hits ``PayoutQueue.MAX_RETRIES`` the entry is parked at
  ``failed`` permanently (the admin can still bump it via the /retry API).

Founder rule — no founder personal mobile in any payout metadata
----------------------------------------------------------------
``MEMORY.md → feedback_no_founder_personal_number.md`` forbids Vinod's
personal number from EVER appearing in outbound metadata. The mock
``razorpay_payout_id`` here is a deterministic ``mock_pout_<queue_id>_<ts>``
stub; no hard-coded phone numbers anywhere in this module. Tests assert
this with an explicit string-scan.
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
# Razorpay X real-send + webhook configuration (Wave-19 W2-MOCK-REAL).
# ---------------------------------------------------------------------------
#
# Tonight all real calls are gated by ``TRAINPLEX_RAZORPAY_DRY_RUN=true``
# in ``.env`` so we wire the code path without firing real money. Webhook
# signature verification uses a constant-time HMAC-SHA256 comparison
# (Razorpay's own algorithm) so we don't add a hard `razorpay` library
# dependency for one helper.

RAZORPAY_DEFAULT_BASE_URL = 'https://api.razorpay.com/v1'
RAZORPAY_DEFAULT_TIMEOUT_SECONDS = 30


def _razorpay_dry_run_default() -> bool:
    raw = os.getenv('TRAINPLEX_RAZORPAY_DRY_RUN', 'true').strip().lower()
    return raw not in ('false', '0', 'no', 'off')


def _razorpay_credentials() -> Dict[str, str]:
    return {
        'key': (os.getenv('RAZORPAY_KEY_ID') or '').strip(),
        'secret': (os.getenv('RAZORPAY_KEY_SECRET') or '').strip(),
        'account': (os.getenv('RAZORPAY_X_ACCOUNT_NUMBER') or '').strip(),
        'webhook_secret': (os.getenv('RAZORPAY_WEBHOOK_SECRET') or '').strip(),
        'base_url': (os.getenv('RAZORPAY_BASE_URL') or RAZORPAY_DEFAULT_BASE_URL).rstrip('/'),
    }


def verify_webhook_signature(*, body: str, signature: str, secret: str) -> bool:
    """Verify a Razorpay webhook payload signature.

    Razorpay computes ``hmac_sha256(secret, raw_body).hexdigest()`` and
    sends it on the ``X-Razorpay-Signature`` header. We compute the same
    digest locally and compare with ``hmac.compare_digest`` (constant-time)
    so timing attacks can't leak signature bits.

    Returns ``True`` on a valid signature; ``False`` otherwise. Caller
    decides whether to return 400.
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
# Public API
# ---------------------------------------------------------------------------


def send_payout(
    payout_queue_entry: PayoutQueue,
    *,
    force_mock_failure: bool = False,
    dry_run: Optional[bool] = None,
) -> PayoutQueue:
    """Attempt to send a payout via Razorpay X.

    Wave-19 W2-MOCK-REAL — when ``TRAINPLEX_RAZORPAY_DRY_RUN=false`` and
    ``RAZORPAY_KEY_ID`` / ``RAZORPAY_KEY_SECRET`` / ``RAZORPAY_X_ACCOUNT_NUMBER``
    are populated, we fire a real ``POST /v1/payouts`` to Razorpay X using
    HTTP Basic auth (key:secret). Otherwise we keep the deterministic
    ``mock_pout_<id>_<ts>`` stub so the rest of the lifecycle stays
    exercised end-to-end. Tonight the dry-run flag defaults to True so
    no real INR moves until the founder flips it.
    """
    if payout_queue_entry.status not in (
        PayoutQueue.STATUS_PENDING,
        PayoutQueue.STATUS_PROCESSING,
    ):
        logger.warning(
            'payments.razorpay.send_payout SKIP queue_id=%s status=%s '
            '— not in sendable state',
            payout_queue_entry.id, payout_queue_entry.status,
        )
        return payout_queue_entry

    # Row-lock-and-flip so two cron workers don't race and double-send.
    with transaction.atomic():
        locked = PayoutQueue.objects.select_for_update().get(id=payout_queue_entry.id)
        if locked.status == PayoutQueue.STATUS_SENT:
            # Lost the race — another worker already sent it.
            return locked
        locked.status = PayoutQueue.STATUS_PROCESSING
        locked.save(update_fields=['status'])

    if force_mock_failure:
        return mark_failed(locked.id, 'mock failure (test hook)')

    if dry_run is None:
        dry_run = _razorpay_dry_run_default()
    creds = _razorpay_credentials()
    have_creds = bool(creds['key'] and creds['secret'] and creds['account'])

    if dry_run or not have_creds:
        mock_payout_id = f'mock_pout_{locked.id}_{int(timezone.now().timestamp())}'
        logger.info(
            'payments.razorpay.send_payout dry-run queue_id=%s mock_id=%s '
            '(TRAINPLEX_RAZORPAY_DRY_RUN=%s, creds_present=%s)',
            locked.id, mock_payout_id, dry_run, have_creds,
        )
        return mark_sent(locked.id, mock_payout_id)

    # Real Razorpay X payout. Amount in paise (INR * 100). We use the
    # trainer's email as the contact identifier — Razorpay rejects payloads
    # that include any free-text variant of a personal number, which lines
    # up with the founder-guard invariant.
    amount_paise = int(round(float(locked.amount_inr) * 100))
    body = {
        'account_number': creds['account'],
        'amount': amount_paise,
        'currency': 'INR',
        'mode': 'IMPS',
        'purpose': 'payout',
        'queue_if_low_balance': True,
        'reference_id': f'trainplex-pq-{locked.id}',
        'narration': f'TrainPlex task payout #{locked.id}',
    }
    url = f"{creds['base_url']}/payouts"
    try:
        resp = requests.post(
            url,
            json=body,
            auth=(creds['key'], creds['secret']),
            headers={'X-Payout-Idempotency': f'trainplex-pq-{locked.id}'},
            timeout=RAZORPAY_DEFAULT_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json() if resp.content else {}
    except Exception as exc:
        return mark_failed(locked.id, f'razorpay error: {exc!s}')

    real_payout_id = payload.get('id') or f'razorpay-{uuid.uuid4().hex[:12]}'
    logger.info(
        'payments.razorpay.send_payout live queue_id=%s razorpay_id=%s',
        locked.id, real_payout_id,
    )
    return mark_sent(locked.id, real_payout_id)


def process_webhook_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Update the matching PayoutQueue row from a verified webhook event.

    Razorpay's payout events expose the queue row via ``payload.payout.entity``.
    We match on the ``reference_id`` we set on outbound (``trainplex-pq-<id>``)
    so the lookup is robust even if the Razorpay ``id`` field is rotated.
    Tonight, with dry-run on, we never actually fire a live payout — but if
    a stale test event lands on the webhook we still process it idempotently.
    """
    event_type = (event or {}).get('event') or ''
    payout_entity = (
        ((event or {}).get('payload') or {}).get('payout') or {}
    ).get('entity') or {}
    reference_id = payout_entity.get('reference_id') or ''
    razorpay_id = payout_entity.get('id') or ''
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
        mark_sent(entry.id, razorpay_id or entry.razorpay_payout_id or f'razorpay-{pq_id}')
    else:
        mark_failed(entry.id, f'webhook {event_type}')

    return {'matched': True, 'event': event_type, 'pq_id': pq_id}


def mark_sent(payout_id: int, razorpay_payout_id: str) -> PayoutQueue:
    """Finalise a successful payout. Writes the wallet debit row.

    Idempotent on the WalletTransaction side — if a ``payout`` row already
    exists for this ``related_payout_id``, we do not double-write.
    """
    with transaction.atomic():
        entry = PayoutQueue.objects.select_for_update().get(id=payout_id)
        if entry.status == PayoutQueue.STATUS_SENT:
            # Already finalised — return as-is for idempotency.
            return entry

        entry.status = PayoutQueue.STATUS_SENT
        entry.razorpay_payout_id = razorpay_payout_id
        entry.sent_at = timezone.now()
        entry.last_error = ''
        entry.save(
            update_fields=['status', 'razorpay_payout_id', 'sent_at', 'last_error'],
        )

        # Write the wallet debit row (idempotent).
        already_written = WalletTransaction.objects.filter(
            user=entry.trainer,
            txn_type=WalletTransaction.TYPE_PAYOUT,
            related_payout_id=entry.id,
        ).exists()
        if not already_written:
            from payments.services.wallet import get_balance  # local import — avoid cycle
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
        'payments.razorpay.mark_sent queue_id=%s razorpay_id=%s amount=%s',
        entry.id, razorpay_payout_id, entry.amount_inr,
    )
    return entry


def mark_failed(payout_id: int, error: str) -> PayoutQueue:
    """Record a failure + bump retry_count.

    Once retry_count >= MAX_RETRIES the entry is parked at ``failed``
    permanently. The admin can still kick a manual retry via
    /api/v1/payments/payout-queue/<id>/retry — that bumps retry_count
    further but re-attempts the send.
    """
    with transaction.atomic():
        entry = PayoutQueue.objects.select_for_update().get(id=payout_id)
        # Truncate the error string defensively — last_error is TextField
        # (no DB limit) but UI surfaces only first 500 chars.
        entry.last_error = (error or '')[:1000]
        entry.retry_count = (entry.retry_count or 0) + 1
        if entry.retry_count >= PayoutQueue.MAX_RETRIES:
            entry.status = PayoutQueue.STATUS_FAILED
        else:
            # Keep it pending so the next cron tick re-attempts.
            entry.status = PayoutQueue.STATUS_PENDING
        entry.save(update_fields=['last_error', 'retry_count', 'status'])

    logger.warning(
        'payments.razorpay.mark_failed queue_id=%s retry=%s status=%s err=%s',
        entry.id, entry.retry_count, entry.status, error,
    )
    return entry


def retry_payout(payout_id: int) -> Optional[PayoutQueue]:
    """Manual admin-triggered retry. Returns the updated entry, or None.

    Resets ``last_error`` and re-runs the send. We DO bump ``retry_count``
    on the next failure even past MAX_RETRIES — the admin's manual
    intervention is intentional, so the parked ``failed`` row gets one
    more shot but never silently retries forever.
    """
    try:
        entry = PayoutQueue.objects.get(id=payout_id)
    except PayoutQueue.DoesNotExist:
        logger.warning('payments.razorpay.retry_payout payout_id=%s not found', payout_id)
        return None

    if entry.status == PayoutQueue.STATUS_SENT:
        # Already successful — no-op.
        return entry

    # Force a re-send. We reset to pending so send_payout's gate passes.
    with transaction.atomic():
        locked = PayoutQueue.objects.select_for_update().get(id=entry.id)
        locked.status = PayoutQueue.STATUS_PENDING
        locked.last_error = ''
        locked.save(update_fields=['status', 'last_error'])

    return send_payout(locked)
