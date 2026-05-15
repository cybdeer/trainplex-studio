# Generated for TrainPlex Phase 1 Step 6.4 + 1.4-G — Payment Release Flow.
#
# Adds the three ``htx_*`` tables that back the consensus-driven payment
# release / hold / payout / refund lifecycle: PayoutQueue, PaymentHold,
# WalletTransaction. See ``label_studio/payments/models.py`` for the full
# design rationale.

import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        # PaymentHold.consensus_result references peer_review.ConsensusResult.
        # The dependency keeps the migration linearizable on a fresh DB.
        ('peer_review', '0001_initial'),
    ]

    operations = [
        # -------------------------------------------------------------------
        # PayoutQueue (declared first so PaymentHold can FK to it)
        # -------------------------------------------------------------------
        migrations.CreateModel(
            name='PayoutQueue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'amount_inr',
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        help_text=(
                            'Gross INR amount. Phase 1 is one-hold-per-payout, '
                            'so this matches the source PaymentHold.amount_inr.'
                        ),
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending (queued, not yet attempted)'),
                            ('processing', 'Processing (Razorpay X call in flight)'),
                            ('sent', 'Sent (Razorpay confirmed)'),
                            ('failed', 'Failed (3 retries exhausted)'),
                        ],
                        default='pending',
                        max_length=16,
                    ),
                ),
                (
                    'razorpay_payout_id',
                    models.CharField(
                        blank=True,
                        default='',
                        help_text=(
                            'Razorpay X payout id (``pout_…``). Empty until the '
                            'mock / real handler confirms. Phase 1 stores a '
                            '``mock_pout_<id>`` stub.'
                        ),
                        max_length=64,
                    ),
                ),
                (
                    'last_error',
                    models.TextField(
                        blank=True,
                        default='',
                        help_text=(
                            'Last failure reason (mock handler / network / '
                            'Razorpay 4xx). Wiped on next successful send. '
                            'Surfaced in the admin retry view.'
                        ),
                    ),
                ),
                (
                    'retry_count',
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text=(
                            'Number of failed attempts so far. Once retry_count '
                            'hits MAX_RETRIES the status is parked at ``failed``.'
                        ),
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                (
                    'trainer',
                    models.ForeignKey(
                        help_text=(
                            'Trainer who receives this payout. PROTECT — never '
                            'silently drop a payout when the user record is deleted.'
                        ),
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='payouts',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Payout queue entry',
                'verbose_name_plural': 'Payout queue entries',
                'db_table': 'htx_payout_queue',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['trainer', '-created_at'], name='htx_pq_trainer_idx'),
                    models.Index(fields=['status', '-created_at'], name='htx_pq_status_idx'),
                ],
            },
        ),
        # -------------------------------------------------------------------
        # PaymentHold
        # -------------------------------------------------------------------
        migrations.CreateModel(
            name='PaymentHold',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'task_id',
                    models.IntegerField(
                        help_text=(
                            'Loose FK-by-value to tasks.Task. One hold per task. '
                            'Matches peer_review.ConsensusResult.task_id.'
                        ),
                        unique=True,
                    ),
                ),
                (
                    'amount_inr',
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        help_text=(
                            'Gross INR. Phase 1 uses a per-task fixed price; '
                            'Phase 2 tier-weighted pricing rides on top.'
                        ),
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('held', 'Held (payment frozen, awaiting consensus)'),
                            ('released', 'Released (consensus approved/flagged, queued)'),
                            ('disputed', 'Disputed (consensus 1/3, QA escalate)'),
                            ('refunded', 'Refunded (consensus rejected)'),
                        ],
                        default='held',
                        max_length=16,
                    ),
                ),
                ('held_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('released_at', models.DateTimeField(blank=True, null=True)),
                (
                    'consensus_result',
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            'FK to peer_review.ConsensusResult once consensus '
                            'has been computed. Null while still in held / '
                            'awaiting reviewers.'
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='payment_holds',
                        to='peer_review.consensusresult',
                    ),
                ),
                (
                    'payout_queue',
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            'PayoutQueue row created on release. Null for held '
                            '/ disputed / refunded outcomes.'
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='source_holds',
                        to='payments.payoutqueue',
                    ),
                ),
                (
                    'trainer',
                    models.ForeignKey(
                        help_text=(
                            'Task submitter — the person who would be paid. '
                            'PROTECT so a deleted user does not silently drop the hold.'
                        ),
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='payment_holds',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Payment hold',
                'verbose_name_plural': 'Payment holds',
                'db_table': 'htx_payment_hold',
                'ordering': ['-held_at'],
                'indexes': [
                    models.Index(fields=['trainer', '-held_at'], name='htx_ph_trainer_idx'),
                    models.Index(fields=['status', '-held_at'], name='htx_ph_status_idx'),
                ],
            },
        ),
        # -------------------------------------------------------------------
        # WalletTransaction
        # -------------------------------------------------------------------
        migrations.CreateModel(
            name='WalletTransaction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'txn_type',
                    models.CharField(
                        choices=[
                            ('hold', 'Held for review'),
                            ('release', 'Released to wallet'),
                            ('payout', 'Sent to UPI'),
                            ('refund', 'Refunded'),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    'amount_inr',
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        help_text=(
                            'Movement amount. Always positive — direction is '
                            'implied by ``txn_type`` (hold/refund are '
                            'zero-impact, release credits, payout debits).'
                        ),
                    ),
                ),
                (
                    'balance_after_inr',
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal('0'),
                        max_digits=12,
                        help_text=(
                            'Trainer balance immediately AFTER this row was '
                            'written. Snapshotted for fast `/wallet` rendering '
                            '— never trust the front-end to recompute.'
                        ),
                    ),
                ),
                (
                    'description',
                    models.CharField(
                        blank=True,
                        default='',
                        help_text=(
                            'Short human-readable description for the wallet '
                            'UI. Phase 1: "Task #<id> hold/release/payout/refund". '
                            'PII-free — must never contain the founder personal '
                            'number or any third-party identifier.'
                        ),
                        max_length=200,
                    ),
                ),
                (
                    'related_task_id',
                    models.IntegerField(
                        blank=True,
                        help_text=(
                            'Loose pointer to the source task. Null for '
                            'non-task movements (Phase 2 referral bonuses etc.).'
                        ),
                        null=True,
                    ),
                ),
                (
                    'related_payout_id',
                    models.IntegerField(
                        blank=True,
                        help_text=(
                            'PayoutQueue id when ``txn_type=payout``. Null otherwise.'
                        ),
                        null=True,
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'user',
                    models.ForeignKey(
                        help_text=(
                            'Trainer the ledger row belongs to. PROTECT to keep '
                            'the ledger immutable.'
                        ),
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='wallet_transactions',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Wallet transaction',
                'verbose_name_plural': 'Wallet transactions',
                'db_table': 'htx_wallet_txn',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', '-created_at'], name='htx_wt_user_idx'),
                    models.Index(fields=['user', 'txn_type', '-created_at'], name='htx_wt_user_type_idx'),
                ],
            },
        ),
    ]
