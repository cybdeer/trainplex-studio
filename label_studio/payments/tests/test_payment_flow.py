"""Tests for the TrainPlex Payment Release Flow — Phase 1 Step 6.4 + 1.4-G.

Covers
------
Payout router (``payments.services.payout_router``):
- approved consensus → PaymentHold released + PayoutQueue created + ledger row.
- flagged consensus → same release path (admin spot-check is out-of-band).
- dispute consensus → hold stays held (status=disputed), no payout.
- rejected consensus → hold refunded, no payout.
- Re-firing consensus is idempotent (no double-release).
- open_payment_hold is idempotent.

Razorpay handler (``payments.services.razorpay_handler``):
- send_payout success → status=sent, razorpay_payout_id stored, wallet debited.
- send_payout failure → retry_count incremented, status=pending again.
- 3 failures → status=failed permanently.
- mark_sent is idempotent (no double-write to WalletTransaction).
- Founder personal mobile NOT in any payout metadata.

Wallet (``payments.services.wallet``):
- get_balance reflects release - payout deltas.
- get_held_balance sums only held rows.

API:
- GET /api/v1/payments/wallet (trainer-only, self).
- GET /api/v1/payments/wallet from another role → 403.
- A trainer fetching wallet only sees their own ledger.
- GET /api/v1/payments/payout-queue (admin-only) lists pending.
- POST /api/v1/payments/payout-queue/<id>/retry (admin-only) bumps retry.
- Trainer hitting admin endpoints → 403.
- GET /api/v1/admin/payment-status (admin-only) returns table + summary.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from payments.models import PaymentHold, PayoutQueue, WalletTransaction
from payments.services import payout_router, razorpay_handler, wallet
from peer_review.models import ConsensusResult, Review, ReviewAssignment
from peer_review.services import consensus_engine

User = get_user_model()


# Founder personal mobile per MEMORY.md → feedback_no_founder_personal_number.
# We assert this string never appears in any outbound payout metadata.
# Literal lives only in `.env` (gitignored); at test time we read it from
# the env var ``TRAINPLEX_FOUNDER_MOBILE_GUARD``, falling back to a
# 10-digit sentinel for CI so this source file never embeds the real value.
import os as _os  # noqa: E402
import re as _re  # noqa: E402

_TEST_SENTINEL_MOBILE = '9876543210'


def _resolve_founder_mobile_variants() -> tuple[str, tuple[str, ...]]:
    raw = _os.environ.get('TRAINPLEX_FOUNDER_MOBILE_GUARD', '').strip()
    digits = _re.sub(r'\D+', '', raw)
    last_ten = digits[-10:] if len(digits) >= 10 else _TEST_SENTINEL_MOBILE
    block5 = last_ten[:5]
    block5b = last_ten[5:]
    return (
        f'+91{last_ten}',
        (
            f'+91{last_ten}',
            f'91{last_ten}',
            last_ten,
            f'+91 {last_ten}',
            f'+91-{last_ten}',
            f'+91 {block5} {block5b}',
        ),
    )


_FOUNDER_PERSONAL_MOBILE, _FOUNDER_PERSONAL_MOBILE_VARIANTS = (
    _resolve_founder_mobile_variants()
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(role: str, suffix: str):
    return User.objects.create_user(
        email=f'{role}-{suffix}@example.test',
        username=f'{role}-{suffix}',
        password='testpass123',
        role=role,
    )


def _open_hold(trainer, task_id: int, amount=Decimal('100.00')) -> PaymentHold:
    return payout_router.open_payment_hold(
        task_id=task_id, trainer=trainer, amount_inr=amount,
    )


def _make_consensus(task_id: int, status: str) -> ConsensusResult:
    """Create a ConsensusResult row in the requested status directly.

    Bypasses the engine so we can drive the router on its own. Saving the
    row also fires the post_save signal which exercises the integration.
    """
    return ConsensusResult.objects.create(
        task_id=task_id,
        total_reviewers=3,
        agreed_count=3 if status == 'approved' else (2 if status == 'flagged' else (1 if status == 'dispute' else 0)),
        disagree_count=0 if status == 'approved' else (1 if status == 'flagged' else (2 if status == 'dispute' else 3)),
        partial_count=0,
        status=status,
        fallback_used=False,
    )


# ===========================================================================
# Payout router — consensus → release / refund / dispute
# ===========================================================================


@pytest.mark.django_db
class TestPayoutRouter(TestCase):

    def setUp(self):
        self.trainer = _make_user('trainer', 'router')

    # ----- approved → release + payout queued -----

    def test_approved_consensus_releases_payment_and_queues_payout(self):
        hold = _open_hold(self.trainer, task_id=601, amount=Decimal('150.00'))
        self.assertEqual(hold.status, PaymentHold.STATUS_HELD)

        # Fire signal via direct ConsensusResult save (post_save).
        _make_consensus(task_id=601, status='approved')

        hold.refresh_from_db()
        self.assertEqual(hold.status, PaymentHold.STATUS_RELEASED)
        self.assertIsNotNone(hold.released_at)
        self.assertIsNotNone(hold.payout_queue_id)

        # PayoutQueue row created.
        pq = PayoutQueue.objects.get(id=hold.payout_queue_id)
        self.assertEqual(pq.trainer_id, self.trainer.id)
        self.assertEqual(pq.amount_inr, Decimal('150.00'))
        self.assertEqual(pq.status, PayoutQueue.STATUS_PENDING)

        # Wallet credit ledger row exists.
        release_rows = WalletTransaction.objects.filter(
            user=self.trainer, txn_type=WalletTransaction.TYPE_RELEASE,
        )
        self.assertEqual(release_rows.count(), 1)
        self.assertEqual(release_rows[0].amount_inr, Decimal('150.00'))
        # Balance after release = 150 (no prior history).
        self.assertEqual(release_rows[0].balance_after_inr, Decimal('150.00'))

    # ----- flagged → release path (same as approved) -----

    def test_flagged_consensus_releases_payment(self):
        hold = _open_hold(self.trainer, task_id=602, amount=Decimal('200.00'))
        _make_consensus(task_id=602, status='flagged')

        hold.refresh_from_db()
        self.assertEqual(hold.status, PaymentHold.STATUS_RELEASED)
        self.assertIsNotNone(hold.payout_queue_id)

        pq = PayoutQueue.objects.get(id=hold.payout_queue_id)
        self.assertEqual(pq.status, PayoutQueue.STATUS_PENDING)
        self.assertEqual(pq.amount_inr, Decimal('200.00'))

    # ----- dispute → hold remains -----

    def test_dispute_consensus_keeps_hold(self):
        hold = _open_hold(self.trainer, task_id=603, amount=Decimal('120.00'))
        _make_consensus(task_id=603, status='dispute')

        hold.refresh_from_db()
        self.assertEqual(hold.status, PaymentHold.STATUS_DISPUTED)
        # No PayoutQueue.
        self.assertIsNone(hold.payout_queue_id)
        self.assertFalse(PayoutQueue.objects.filter(trainer=self.trainer).exists())
        # No `release` ledger row.
        self.assertFalse(
            WalletTransaction.objects.filter(
                user=self.trainer, txn_type=WalletTransaction.TYPE_RELEASE,
            ).exists()
        )

    # ----- rejected → refund -----

    def test_rejected_consensus_refunds_hold(self):
        hold = _open_hold(self.trainer, task_id=604, amount=Decimal('80.00'))
        _make_consensus(task_id=604, status='rejected')

        hold.refresh_from_db()
        self.assertEqual(hold.status, PaymentHold.STATUS_REFUNDED)
        self.assertIsNone(hold.payout_queue_id)
        # Refund ledger row written; no balance change.
        refund_rows = WalletTransaction.objects.filter(
            user=self.trainer, txn_type=WalletTransaction.TYPE_REFUND,
        )
        self.assertEqual(refund_rows.count(), 1)
        self.assertEqual(refund_rows[0].balance_after_inr, Decimal('0'))

    # ----- idempotency -----

    def test_re_firing_consensus_does_not_double_release(self):
        _open_hold(self.trainer, task_id=605, amount=Decimal('100.00'))
        cr = _make_consensus(task_id=605, status='approved')
        # Trigger the signal again by re-saving the consensus.
        cr.save()

        # Should still be ONE PayoutQueue row, ONE release WalletTransaction.
        self.assertEqual(
            PayoutQueue.objects.filter(trainer=self.trainer).count(), 1,
        )
        self.assertEqual(
            WalletTransaction.objects.filter(
                user=self.trainer, txn_type=WalletTransaction.TYPE_RELEASE,
            ).count(),
            1,
        )

    def test_open_payment_hold_is_idempotent(self):
        h1 = _open_hold(self.trainer, task_id=606, amount=Decimal('50.00'))
        h2 = _open_hold(self.trainer, task_id=606, amount=Decimal('50.00'))
        self.assertEqual(h1.id, h2.id)
        # And only one `hold` ledger row.
        self.assertEqual(
            WalletTransaction.objects.filter(
                user=self.trainer, txn_type=WalletTransaction.TYPE_HOLD,
                related_task_id=606,
            ).count(),
            1,
        )

    # ----- ledger row written on hold -----

    def test_open_payment_hold_writes_hold_ledger_row(self):
        _open_hold(self.trainer, task_id=607, amount=Decimal('75.50'))
        hold_rows = WalletTransaction.objects.filter(
            user=self.trainer, txn_type=WalletTransaction.TYPE_HOLD,
            related_task_id=607,
        )
        self.assertEqual(hold_rows.count(), 1)
        # Balance after hold = unchanged (still 0).
        self.assertEqual(hold_rows[0].balance_after_inr, Decimal('0'))
        # Description PII-free.
        self.assertIn('607', hold_rows[0].description)


# ===========================================================================
# Razorpay handler (MOCK)
# ===========================================================================


@pytest.mark.django_db
class TestRazorpayHandler(TestCase):

    def setUp(self):
        self.trainer = _make_user('trainer', 'razorpay')

    def _make_payout(self, amount=Decimal('100.00')) -> PayoutQueue:
        return PayoutQueue.objects.create(
            trainer=self.trainer, amount_inr=amount,
        )

    def test_send_payout_success_marks_sent_and_debits_wallet(self):
        # Pre-credit the wallet so payout has something to debit.
        _open_hold(self.trainer, task_id=701, amount=Decimal('100.00'))
        _make_consensus(task_id=701, status='approved')
        pq = PayoutQueue.objects.get(trainer=self.trainer)

        sent = razorpay_handler.send_payout(pq)
        self.assertEqual(sent.status, PayoutQueue.STATUS_SENT)
        self.assertTrue(sent.razorpay_payout_id.startswith('mock_pout_'))
        self.assertIsNotNone(sent.sent_at)

        # Wallet debit row.
        debit = WalletTransaction.objects.filter(
            user=self.trainer, txn_type=WalletTransaction.TYPE_PAYOUT,
        )
        self.assertEqual(debit.count(), 1)
        self.assertEqual(debit[0].balance_after_inr, Decimal('0'))

    def test_send_payout_failure_increments_retry_and_returns_to_pending(self):
        pq = self._make_payout()
        result = razorpay_handler.send_payout(pq, force_mock_failure=True)
        self.assertEqual(result.retry_count, 1)
        self.assertEqual(result.status, PayoutQueue.STATUS_PENDING)
        self.assertIn('mock failure', result.last_error)

    def test_three_failures_marks_permanently_failed(self):
        pq = self._make_payout()
        for _ in range(3):
            razorpay_handler.send_payout(pq, force_mock_failure=True)
            pq.refresh_from_db()
        self.assertEqual(pq.retry_count, 3)
        self.assertEqual(pq.status, PayoutQueue.STATUS_FAILED)

    def test_mark_sent_is_idempotent(self):
        _open_hold(self.trainer, task_id=702, amount=Decimal('100.00'))
        _make_consensus(task_id=702, status='approved')
        pq = PayoutQueue.objects.get(trainer=self.trainer)
        razorpay_handler.send_payout(pq)
        razorpay_handler.mark_sent(pq.id, 'mock_pout_repeat')  # no-op
        debit_rows = WalletTransaction.objects.filter(
            user=self.trainer, txn_type=WalletTransaction.TYPE_PAYOUT,
        )
        # Still exactly ONE payout ledger row.
        self.assertEqual(debit_rows.count(), 1)

    def test_retry_payout_re_attempts_failed(self):
        pq = self._make_payout()
        # Three failures park it at failed.
        for _ in range(3):
            razorpay_handler.send_payout(pq, force_mock_failure=True)
            pq.refresh_from_db()
        self.assertEqual(pq.status, PayoutQueue.STATUS_FAILED)
        # Admin retry kicks one more attempt — defaults to success in our
        # mock (no force_mock_failure).
        retried = razorpay_handler.retry_payout(pq.id)
        self.assertEqual(retried.status, PayoutQueue.STATUS_SENT)
        self.assertTrue(retried.razorpay_payout_id.startswith('mock_pout_'))

    def test_founder_personal_mobile_not_in_payout_metadata(self):
        """Founder personal mobile must NEVER appear in any outbound metadata.

        MEMORY.md → feedback_no_founder_personal_number.md.
        """
        _open_hold(self.trainer, task_id=703, amount=Decimal('150.00'))
        _make_consensus(task_id=703, status='approved')
        pq = PayoutQueue.objects.get(trainer=self.trainer)
        sent = razorpay_handler.send_payout(pq)

        # Scan all string fields written by the handler.
        candidates = [
            sent.razorpay_payout_id or '',
            sent.last_error or '',
        ]
        for txn in WalletTransaction.objects.all():
            candidates.append(txn.description or '')
        for h in PaymentHold.objects.all():
            candidates.append(str(h.task_id))
        joined = ' | '.join(candidates).lower()
        for variant in _FOUNDER_PERSONAL_MOBILE_VARIANTS:
            self.assertNotIn(
                variant.lower().replace(' ', '').replace('-', ''),
                joined.replace(' ', '').replace('-', ''),
                f'Founder personal mobile variant {variant!r} leaked into payout '
                f'metadata: {candidates!r}',
            )


# ===========================================================================
# Wallet service
# ===========================================================================


@pytest.mark.django_db
class TestWalletService(TestCase):

    def setUp(self):
        self.trainer = _make_user('trainer', 'wallet')

    def test_get_balance_reflects_release_minus_payout(self):
        # Two release events → ₹250 balance.
        for tid in (801, 802):
            _open_hold(self.trainer, task_id=tid, amount=Decimal('125.00'))
            _make_consensus(task_id=tid, status='approved')
        self.assertEqual(wallet.get_balance(self.trainer), Decimal('250.00'))

        # Send one payout → balance drops back to 125.
        pq = PayoutQueue.objects.first()
        razorpay_handler.send_payout(pq)
        self.assertEqual(wallet.get_balance(self.trainer), Decimal('125.00'))

    def test_get_held_balance_sums_only_held_rows(self):
        # Open two holds, only release one.
        _open_hold(self.trainer, task_id=803, amount=Decimal('40.00'))
        _open_hold(self.trainer, task_id=804, amount=Decimal('60.00'))
        _make_consensus(task_id=803, status='approved')
        # Only task_id=804 remains held.
        self.assertEqual(wallet.get_held_balance(self.trainer), Decimal('60.00'))

    def test_get_recent_transactions_caps_at_100(self):
        for i in range(120):
            WalletTransaction.objects.create(
                user=self.trainer,
                txn_type=WalletTransaction.TYPE_HOLD,
                amount_inr=Decimal('1.00'),
                description=f'#{i}',
            )
        txns = wallet.get_recent_transactions(self.trainer, limit=500)
        self.assertEqual(len(txns), 100)

    def test_compute_trainer_balance_matches_snapshot(self):
        _open_hold(self.trainer, task_id=805, amount=Decimal('300.00'))
        _make_consensus(task_id=805, status='approved')
        self.assertEqual(
            wallet.compute_trainer_balance(self.trainer),
            wallet.get_balance(self.trainer),
        )


# ===========================================================================
# API endpoints
# ===========================================================================


@pytest.mark.django_db
class TestPaymentsAPI(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.trainer = _make_user('trainer', 'api')
        self.trainer_other = _make_user('trainer', 'api-other')
        self.admin = _make_user('admin', 'api')
        self.reviewer = _make_user('reviewer', 'api')

    # ----- /api/v1/payments/wallet -----

    def test_trainer_wallet_self_only_returns_balance_and_txns(self):
        _open_hold(self.trainer, task_id=901, amount=Decimal('100.00'))
        _make_consensus(task_id=901, status='approved')
        self.client.force_authenticate(user=self.trainer)
        res = self.client.get('/api/v1/payments/wallet')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['balance_inr'], '100.00')
        self.assertEqual(body['held_inr'], '0.00')
        # transactions: hold + release.
        self.assertGreaterEqual(len(body['transactions']), 2)

    def test_trainer_wallet_blocks_non_trainer(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/payments/wallet')
        self.assertEqual(res.status_code, 403)
        self.client.force_authenticate(user=self.reviewer)
        res = self.client.get('/api/v1/payments/wallet')
        self.assertEqual(res.status_code, 403)

    def test_trainer_only_sees_own_ledger(self):
        # Other trainer has rows; we MUST not see them.
        _open_hold(self.trainer_other, task_id=902, amount=Decimal('200.00'))
        _make_consensus(task_id=902, status='approved')
        # Self has nothing.
        self.client.force_authenticate(user=self.trainer)
        res = self.client.get('/api/v1/payments/wallet')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['balance_inr'], '0.00')
        self.assertEqual(body['transactions'], [])

    # ----- /api/v1/payments/payout-queue -----

    def test_admin_payout_queue_lists_pending(self):
        _open_hold(self.trainer, task_id=903, amount=Decimal('60.00'))
        _make_consensus(task_id=903, status='approved')
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/payments/payout-queue')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['total'], 1)
        self.assertEqual(body['results'][0]['status'], 'pending')
        self.assertEqual(body['results'][0]['trainer_id'], self.trainer.id)

    def test_admin_payout_queue_blocks_non_admin(self):
        self.client.force_authenticate(user=self.trainer)
        res = self.client.get('/api/v1/payments/payout-queue')
        self.assertEqual(res.status_code, 403)

    def test_admin_payout_retry_bumps_retry_count(self):
        _open_hold(self.trainer, task_id=904, amount=Decimal('70.00'))
        _make_consensus(task_id=904, status='approved')
        pq = PayoutQueue.objects.get(trainer=self.trainer)
        # Park it at failed by 3 forced failures.
        for _ in range(3):
            razorpay_handler.send_payout(pq, force_mock_failure=True)
            pq.refresh_from_db()
        self.assertEqual(pq.status, PayoutQueue.STATUS_FAILED)

        self.client.force_authenticate(user=self.admin)
        res = self.client.post(f'/api/v1/payments/payout-queue/{pq.id}/retry')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        # In the mock, retry succeeds → status=sent.
        self.assertEqual(body['payout']['status'], 'sent')
        # retry_count remains 3 (mark_sent doesn't bump it).
        pq.refresh_from_db()
        self.assertEqual(pq.retry_count, 3)

    def test_admin_payout_retry_blocks_non_admin(self):
        _open_hold(self.trainer, task_id=905, amount=Decimal('25.00'))
        _make_consensus(task_id=905, status='approved')
        pq = PayoutQueue.objects.get(trainer=self.trainer)
        self.client.force_authenticate(user=self.trainer)
        res = self.client.post(f'/api/v1/payments/payout-queue/{pq.id}/retry')
        self.assertEqual(res.status_code, 403)

    # ----- /api/v1/admin/payment-status -----

    def test_admin_payment_status_returns_table_and_summary(self):
        _open_hold(self.trainer, task_id=906, amount=Decimal('20.00'))
        _make_consensus(task_id=906, status='approved')
        _open_hold(self.trainer, task_id=907, amount=Decimal('30.00'))
        _make_consensus(task_id=907, status='rejected')

        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/payment-status')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['total'], 2)
        self.assertEqual(body['summary']['released'], 1)
        self.assertEqual(body['summary']['refunded'], 1)

    def test_admin_payment_status_filter_by_status(self):
        _open_hold(self.trainer, task_id=908, amount=Decimal('10.00'))
        _make_consensus(task_id=908, status='approved')
        _open_hold(self.trainer, task_id=909, amount=Decimal('10.00'))
        _make_consensus(task_id=909, status='dispute')

        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/payment-status?status=disputed')
        body = res.json()
        self.assertEqual(body['total'], 1)
        self.assertEqual(body['results'][0]['status'], 'disputed')

    def test_admin_payment_status_blocks_non_admin(self):
        self.client.force_authenticate(user=self.trainer)
        res = self.client.get('/api/v1/admin/payment-status')
        self.assertEqual(res.status_code, 403)
