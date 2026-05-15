"""TrainPlex payments models — Phase 1 Step 6.4 + Step 1.4-G.

Three tables back the consensus-driven payment release flow:

* ``PaymentHold`` (``htx_payment_hold``) — one row per task. Opens when the
  trainer submits the task, holds the gross INR amount, then flips to
  ``released`` / ``refunded`` based on the ``ConsensusResult.status`` flip
  from ``peer_review``. ``payout_queue`` FK is populated only after release.

* ``PayoutQueue`` (``htx_payout_queue``) — outbound Razorpay X payout entries.
  Status walks ``pending → processing → sent`` (or ``failed`` after 3
  retries). One ``PaymentHold`` releases into at most one ``PayoutQueue``
  row; the queue may bundle multiple holds in a future cadence (Phase 2),
  but Phase 1 ships 1-hold-per-payout for traceability.

* ``WalletTransaction`` (``htx_wallet_txn``) — append-only ledger over every
  hold / release / payout / refund. ``balance_after_inr`` snapshots the
  trainer's running balance for fast `/wallet` rendering without a
  re-aggregate per request.

Phase 1 status
--------------
* ``task_id`` is a loose integer (no hard FK to ``tasks.Task``) — same
  pattern as ``peer_review.ReviewAssignment.task_id``. Hard-deleted /
  synthetic tasks must not orphan-purge the ledger.
* ``razorpay_payout_id`` is empty in Phase 1 — the mock handler in
  ``payments.services.razorpay_handler`` returns a stub id. Real wiring +
  prod credentials land Phase 2.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# PayoutQueue (declared first so PaymentHold can FK to it)
# ---------------------------------------------------------------------------


class PayoutQueue(models.Model):
    """Outbound Razorpay X payout entry. Walks pending → processing → sent."""

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending (queued, not yet attempted)'),
        (STATUS_PROCESSING, 'Processing (Razorpay X call in flight)'),
        (STATUS_SENT, 'Sent (Razorpay confirmed)'),
        (STATUS_FAILED, 'Failed (3 retries exhausted)'),
    ]

    # Max automatic retries before a payout is parked at ``failed``. The
    # admin retry endpoint can bump it manually (forces one more attempt),
    # but the auto-retry caps here.
    MAX_RETRIES = 3

    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payouts',
        help_text=_('Trainer who receives this payout. PROTECT — never silently '
                    'drop a payout when the user record is deleted.'),
    )

    amount_inr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_('Gross INR amount. Phase 1 is one-hold-per-payout, so this '
                    'matches the source PaymentHold.amount_inr.'),
    )

    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    razorpay_payout_id = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text=_('Razorpay X payout id (``pout_…``). Empty until the mock / '
                    'real handler confirms. Phase 1 stores a ``mock_pout_<id>`` '
                    'stub.'),
    )

    last_error = models.TextField(
        blank=True,
        default='',
        help_text=_('Last failure reason (mock handler / network / Razorpay 4xx). '
                    'Wiped on next successful send. Surfaced in the admin retry view.'),
    )

    retry_count = models.PositiveSmallIntegerField(
        default=0,
        help_text=_('Number of failed attempts so far. Once retry_count hits '
                    'MAX_RETRIES the status is parked at ``failed``.'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'htx_payout_queue'
        verbose_name = _('Payout queue entry')
        verbose_name_plural = _('Payout queue entries')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['trainer', '-created_at'], name='htx_pq_trainer_idx'),
            models.Index(fields=['status', '-created_at'], name='htx_pq_status_idx'),
        ]

    def __str__(self):  # pragma: no cover  (display only)
        return (
            f'PayoutQueue(id={self.id}, trainer_id={self.trainer_id}, '
            f'amount={self.amount_inr}, status={self.status})'
        )


# ---------------------------------------------------------------------------
# PaymentHold
# ---------------------------------------------------------------------------


class PaymentHold(models.Model):
    """One row per task. Frozen INR amount until consensus resolves."""

    STATUS_HELD = 'held'
    STATUS_RELEASED = 'released'
    STATUS_DISPUTED = 'disputed'
    STATUS_REFUNDED = 'refunded'

    STATUS_CHOICES = [
        (STATUS_HELD, 'Held (payment frozen, awaiting consensus)'),
        (STATUS_RELEASED, 'Released (consensus approved/flagged, queued)'),
        (STATUS_DISPUTED, 'Disputed (consensus 1/3, QA escalate)'),
        (STATUS_REFUNDED, 'Refunded (consensus rejected)'),
    ]

    task_id = models.IntegerField(
        unique=True,
        help_text=_('Loose FK-by-value to tasks.Task. One hold per task. '
                    'Matches peer_review.ConsensusResult.task_id.'),
    )

    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payment_holds',
        help_text=_('Task submitter — the person who would be paid. PROTECT so '
                    'a deleted user does not silently drop the hold.'),
    )

    amount_inr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_('Gross INR. Phase 1 uses a per-task fixed price; Phase 2 '
                    'tier-weighted pricing rides on top.'),
    )

    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_HELD,
    )

    held_at = models.DateTimeField(default=timezone.now)
    released_at = models.DateTimeField(null=True, blank=True)

    consensus_result = models.ForeignKey(
        'peer_review.ConsensusResult',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_holds',
        help_text=_('FK to peer_review.ConsensusResult once consensus has been '
                    'computed. Null while still in held / awaiting reviewers.'),
    )

    payout_queue = models.ForeignKey(
        PayoutQueue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_holds',
        help_text=_('PayoutQueue row created on release. Null for held / '
                    'disputed / refunded outcomes.'),
    )

    class Meta:
        db_table = 'htx_payment_hold'
        verbose_name = _('Payment hold')
        verbose_name_plural = _('Payment holds')
        ordering = ['-held_at']
        indexes = [
            models.Index(fields=['trainer', '-held_at'], name='htx_ph_trainer_idx'),
            models.Index(fields=['status', '-held_at'], name='htx_ph_status_idx'),
        ]

    def __str__(self):  # pragma: no cover  (display only)
        return (
            f'PaymentHold(id={self.id}, task_id={self.task_id}, '
            f'trainer_id={self.trainer_id}, amount={self.amount_inr}, '
            f'status={self.status})'
        )


# ---------------------------------------------------------------------------
# WalletTransaction
# ---------------------------------------------------------------------------


class WalletTransaction(models.Model):
    """Append-only ledger over every wallet movement.

    A row is written for each of:
        * ``hold``    — trainer submits, gross amount frozen (no balance change).
        * ``release`` — consensus approves/flags, amount lands in wallet.
        * ``payout``  — Razorpay payout dispatched (wallet debited).
        * ``refund``  — consensus rejects, hold reversed (no balance change).

    For ``hold`` + ``refund`` the wallet balance does NOT move — those rows
    exist purely so the `recent transactions` UI can show the trainer the
    full lifecycle. The ``release`` row credits the wallet; the ``payout``
    row debits it.
    """

    TYPE_HOLD = 'hold'
    TYPE_RELEASE = 'release'
    TYPE_PAYOUT = 'payout'
    TYPE_REFUND = 'refund'

    TYPE_CHOICES = [
        (TYPE_HOLD, 'Held for review'),
        (TYPE_RELEASE, 'Released to wallet'),
        (TYPE_PAYOUT, 'Sent to UPI'),
        (TYPE_REFUND, 'Refunded'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='wallet_transactions',
        help_text=_('Trainer the ledger row belongs to. PROTECT to keep the '
                    'ledger immutable.'),
    )

    txn_type = models.CharField(
        max_length=16,
        choices=TYPE_CHOICES,
    )

    amount_inr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_('Movement amount. Always positive — direction is implied '
                    'by ``txn_type`` (hold/refund are zero-impact, release '
                    'credits, payout debits).'),
    )

    balance_after_inr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text=_('Trainer balance immediately AFTER this row was written. '
                    'Snapshotted for fast `/wallet` rendering — never trust '
                    'the front-end to recompute.'),
    )

    description = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text=_('Short human-readable description for the wallet UI. '
                    'Phase 1: "Task #<id> hold/release/payout/refund". '
                    'PII-free — must never contain the founder personal '
                    'number or any third-party identifier.'),
    )

    related_task_id = models.IntegerField(
        null=True,
        blank=True,
        help_text=_('Loose pointer to the source task. Null for non-task '
                    'movements (Phase 2 referral bonuses etc.).'),
    )

    related_payout_id = models.IntegerField(
        null=True,
        blank=True,
        help_text=_('PayoutQueue id when ``txn_type=payout``. Null otherwise.'),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'htx_wallet_txn'
        verbose_name = _('Wallet transaction')
        verbose_name_plural = _('Wallet transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='htx_wt_user_idx'),
            models.Index(fields=['user', 'txn_type', '-created_at'], name='htx_wt_user_type_idx'),
        ]

    def __str__(self):  # pragma: no cover  (display only)
        return (
            f'WalletTransaction(id={self.id}, user_id={self.user_id}, '
            f'type={self.txn_type}, amount={self.amount_inr}, '
            f'balance_after={self.balance_after_inr})'
        )
