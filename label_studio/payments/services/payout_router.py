"""TrainPlex payments — consensus event router.

Phase 1 Step 6.4. The single entry point from the ``peer_review`` flow
into the payment side. Listens for ``ConsensusResult.post_save`` (signal
hooked in ``payments.signals``) and dispatches by status:

    approved | flagged → release_payment(hold) → PayoutQueue + WalletTransaction
    dispute            → mark hold disputed (payment HOLD, QA escalates)
    rejected           → refund_hold(hold) (no payout, no balance change)

Idempotency
-----------
* Re-firing the signal for the same ConsensusResult row is a no-op for
  already-resolved holds. We only mutate when the hold is in `held`.
* ``open_payment_hold(task_id, trainer, amount)`` is the public surface
  used by the task-submit flow (Step 1.4-G). Idempotent — second call
  for the same task returns the existing hold (does NOT double-hold).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone

from payments.models import PaymentHold, PayoutQueue, WalletTransaction
# Wave-19 W2-PAYOUT (2026-05-16): route via payout_provider shim so the
# active provider (Razorpay rollback / ShivGateway active) is one env-var
# flip away. Public surface matches razorpay_handler 1:1.
from payments.services import payout_provider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API — task-submit side (Step 1.4-G)
# ---------------------------------------------------------------------------


def open_payment_hold(
    *,
    task_id: int,
    trainer,
    amount_inr,
) -> PaymentHold:
    """Open a PaymentHold for a freshly submitted task.

    Called by the trainer task-submit flow when the task lands in
    ``pending_review``. Writes a matching ``hold`` row to the
    WalletTransaction ledger so the trainer sees "₹X awaiting review"
    immediately in the wallet UI.

    Idempotent — second call for the same task returns the existing hold.
    """
    amount = Decimal(str(amount_inr))
    if amount <= 0:
        raise ValueError(f'amount_inr must be positive, got {amount_inr!r}')

    existing = PaymentHold.objects.filter(task_id=task_id).first()
    if existing is not None:
        return existing

    with transaction.atomic():
        hold = PaymentHold.objects.create(
            task_id=task_id,
            trainer=trainer,
            amount_inr=amount,
            status=PaymentHold.STATUS_HELD,
        )
        # Wallet ledger: hold rows do NOT change the balance, but we still
        # write one so the trainer's wallet shows the full lifecycle.
        from payments.services.wallet import get_balance  # local — avoid cycle
        current_balance = get_balance(trainer)
        WalletTransaction.objects.create(
            user=trainer,
            txn_type=WalletTransaction.TYPE_HOLD,
            amount_inr=amount,
            balance_after_inr=current_balance,
            description=f'Task #{task_id} held for review',
            related_task_id=task_id,
        )

    logger.info(
        'payments.router.open_hold task_id=%s trainer_id=%s amount=%s',
        task_id, trainer.id, amount,
    )
    return hold


# ---------------------------------------------------------------------------
# Public API — consensus event side (Step 6.4)
# ---------------------------------------------------------------------------


def on_consensus_computed(consensus_result) -> Optional[PaymentHold]:
    """Signal-handler entry: route the consensus outcome to release / refund.

    Returns the affected PaymentHold (or None when no matching hold exists,
    e.g. the peer_review tests that don't open a hold).
    """
    if consensus_result is None or not getattr(consensus_result, 'task_id', None):
        return None

    try:
        hold = PaymentHold.objects.get(task_id=consensus_result.task_id)
    except PaymentHold.DoesNotExist:
        # peer_review can be exercised in isolation (its tests don't open
        # holds), so missing-hold is a clean no-op, not an error.
        logger.debug(
            'payments.router.on_consensus_computed SKIP task_id=%s — no hold',
            consensus_result.task_id,
        )
        return None

    if hold.status != PaymentHold.STATUS_HELD:
        # Already resolved — second consensus fire shouldn't reverse the
        # outcome. Idempotent no-op.
        logger.debug(
            'payments.router.on_consensus_computed SKIP hold_id=%s status=%s',
            hold.id, hold.status,
        )
        return hold

    # Bind the consensus row to the hold for the audit trail.
    hold.consensus_result = consensus_result

    status = consensus_result.status
    if status in ('approved', 'flagged'):
        return release_payment(hold)
    if status == 'dispute':
        return _mark_disputed(hold)
    if status == 'rejected':
        return refund_hold(hold)

    # Unknown status — defensive. Persist the consensus FK but leave the
    # hold alone so an admin can investigate.
    hold.save(update_fields=['consensus_result'])
    logger.error(
        'payments.router.on_consensus_computed UNKNOWN status=%r hold_id=%s',
        status, hold.id,
    )
    return hold


# ---------------------------------------------------------------------------
# Release / refund / dispute mutators
# ---------------------------------------------------------------------------


def release_payment(payment_hold: PaymentHold) -> PaymentHold:
    """Move a PaymentHold from `held` → `released` and queue a payout.

    Side effects (all in one atomic block):
        1. Create the PayoutQueue entry (status=pending).
        2. Write the `release` WalletTransaction row — credits the wallet.
        3. Flip PaymentHold.status = released, link payout_queue, set released_at.

    Returns the updated PaymentHold.
    """
    if payment_hold.status != PaymentHold.STATUS_HELD:
        logger.debug(
            'payments.router.release SKIP hold_id=%s status=%s',
            payment_hold.id, payment_hold.status,
        )
        return payment_hold

    with transaction.atomic():
        # Re-lock so concurrent consensus-fires don't race.
        hold = PaymentHold.objects.select_for_update().get(id=payment_hold.id)
        if hold.status != PaymentHold.STATUS_HELD:
            return hold

        payout = PayoutQueue.objects.create(
            trainer=hold.trainer,
            amount_inr=hold.amount_inr,
            status=PayoutQueue.STATUS_PENDING,
        )

        # Wallet credit row.
        from payments.services.wallet import get_balance  # local — avoid cycle
        current_balance = get_balance(hold.trainer)
        new_balance = current_balance + hold.amount_inr
        WalletTransaction.objects.create(
            user=hold.trainer,
            txn_type=WalletTransaction.TYPE_RELEASE,
            amount_inr=hold.amount_inr,
            balance_after_inr=new_balance,
            description=f'Task #{hold.task_id} released to wallet',
            related_task_id=hold.task_id,
        )

        hold.status = PaymentHold.STATUS_RELEASED
        hold.released_at = timezone.now()
        hold.payout_queue = payout
        # consensus_result already set by caller (on_consensus_computed).
        hold.save(update_fields=[
            'status', 'released_at', 'payout_queue', 'consensus_result',
        ])

    logger.info(
        'payments.router.release hold_id=%s task_id=%s payout_id=%s amount=%s',
        hold.id, hold.task_id, payout.id, hold.amount_inr,
    )
    return hold


def refund_hold(payment_hold: PaymentHold) -> PaymentHold:
    """Move a PaymentHold from `held` → `refunded`. No wallet credit.

    The `refund` ledger row is informational — the trainer never had
    spendable money to begin with. Description nudges them toward the
    next batch.
    """
    if payment_hold.status != PaymentHold.STATUS_HELD:
        return payment_hold

    with transaction.atomic():
        hold = PaymentHold.objects.select_for_update().get(id=payment_hold.id)
        if hold.status != PaymentHold.STATUS_HELD:
            return hold

        from payments.services.wallet import get_balance  # local — avoid cycle
        current_balance = get_balance(hold.trainer)
        WalletTransaction.objects.create(
            user=hold.trainer,
            txn_type=WalletTransaction.TYPE_REFUND,
            amount_inr=hold.amount_inr,
            balance_after_inr=current_balance,  # no change to balance
            description=f'Task #{hold.task_id} rejected — no payout',
            related_task_id=hold.task_id,
        )

        hold.status = PaymentHold.STATUS_REFUNDED
        hold.released_at = timezone.now()
        hold.save(update_fields=[
            'status', 'released_at', 'consensus_result',
        ])

    logger.info(
        'payments.router.refund hold_id=%s task_id=%s amount=%s',
        hold.id, hold.task_id, hold.amount_inr,
    )
    return hold


def _mark_disputed(payment_hold: PaymentHold) -> PaymentHold:
    """Flip status to `disputed`. Wallet ledger UNCHANGED — money still held.

    No wallet ledger row is written: a dispute does not change the
    trainer's balance or even their "money on the line" view, only the
    status badge. QA's resolution will reverse this to released or
    refunded via a follow-up call.
    """
    if payment_hold.status != PaymentHold.STATUS_HELD:
        return payment_hold

    with transaction.atomic():
        hold = PaymentHold.objects.select_for_update().get(id=payment_hold.id)
        if hold.status != PaymentHold.STATUS_HELD:
            return hold
        hold.status = PaymentHold.STATUS_DISPUTED
        hold.save(update_fields=['status', 'consensus_result'])

    logger.info(
        'payments.router.dispute hold_id=%s task_id=%s',
        hold.id, hold.task_id,
    )
    return hold


# ---------------------------------------------------------------------------
# Payout cron tick (Phase 2 — schedule via systemd / django_rq)
# ---------------------------------------------------------------------------


def flush_pending_payouts(limit: int = 50) -> int:
    """Best-effort tick: walk pending payouts and send them via the handler.

    Phase 1 ships this as a callable (no scheduler yet); tests invoke it
    directly. Phase 2 wires a periodic cron tick (same pattern as
    ``peer_review.timeout_sweep``).

    Returns the number of payouts attempted (sent or marked failed).
    """
    pending = PayoutQueue.objects.filter(
        status__in=[PayoutQueue.STATUS_PENDING, PayoutQueue.STATUS_PROCESSING],
    ).order_by('created_at')[:limit]

    attempted = 0
    for entry in pending:
        try:
            payout_provider.send_payout(entry)
        except Exception as exc:  # pragma: no cover  (defensive)
            logger.exception('flush_pending_payouts queue_id=%s err=%s', entry.id, exc)
            payout_provider.mark_failed(entry.id, str(exc))
        attempted += 1
    return attempted
