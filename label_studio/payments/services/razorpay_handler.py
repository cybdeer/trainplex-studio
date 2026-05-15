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

import logging
from typing import Optional

from django.db import transaction
from django.utils import timezone

from payments.models import PayoutQueue, WalletTransaction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def send_payout(
    payout_queue_entry: PayoutQueue,
    *,
    force_mock_failure: bool = False,
) -> PayoutQueue:
    """Attempt to send a payout via Razorpay X.

    Phase 1 — MOCK. The handler:
        * Validates the entry is in a sendable state (pending or processing).
        * Flips status to ``processing`` (atomic, with row-lock).
        * Synthesises a ``mock_pout_<id>_<ts>`` payout id.
        * Calls ``mark_sent`` (success) or ``mark_failed`` if
          ``force_mock_failure=True`` (test hook).

    Phase 2 — REAL. Replace the ``mock_pout`` stub with the actual
    ``razorpay_client.payout.create(...)`` call. Same return contract.
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

    # ---- BEGIN MOCK Razorpay call ----
    # Phase 2 swap: client = razorpay.Client(auth=(KEY, SECRET))
    #               response = client.payout.create({...})
    #               return mark_sent(locked.id, response['id'])
    if force_mock_failure:
        return mark_failed(locked.id, 'mock failure (test hook)')

    mock_payout_id = f'mock_pout_{locked.id}_{int(timezone.now().timestamp())}'
    # ---- END MOCK Razorpay call ----

    return mark_sent(locked.id, mock_payout_id)


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
