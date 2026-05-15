# Generated for TrainPlex Phase 1 Step 6 — Reviewer queue + consensus engine.
#
# Adds the four ``htx_*`` tables that back the 3-reviewer consensus + dispute
# flow: ReviewAssignment, Review, ConsensusResult, Dispute. See
# ``label_studio/peer_review/models.py`` for the full design rationale.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # -------------------------------------------------------------------
        # ReviewAssignment
        # -------------------------------------------------------------------
        migrations.CreateModel(
            name='ReviewAssignment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'task_id',
                    models.IntegerField(
                        help_text=(
                            'Loose FK-by-value to tasks.Task. Phase 1 keeps this a '
                            'plain integer so a synthetic / hard-deleted task does not '
                            'orphan-purge the review trail.'
                        ),
                    ),
                ),
                (
                    'trainer_id',
                    models.IntegerField(
                        blank=True,
                        help_text=(
                            'Snapshot of the task submitter id for fast queue rendering '
                            'and the cooldown check (same reviewer should not review the '
                            'same trainer within 7 days).'
                        ),
                        null=True,
                    ),
                ),
                ('assigned_at', models.DateTimeField(default=django.utils.timezone.now)),
                (
                    'deadline_at',
                    models.DateTimeField(
                        help_text=(
                            'Auto-set to assigned_at + 48h by reviewer_assigner. '
                            'The timeout sweep flips status to "expired" past this point.'
                        ),
                    ),
                ),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending'),
                            ('in_progress', 'In progress'),
                            ('done', 'Done'),
                            ('expired', 'Expired (timeout)'),
                        ],
                        default='pending',
                        max_length=16,
                    ),
                ),
                (
                    'reviewer',
                    models.ForeignKey(
                        help_text=(
                            'The reviewer User. Must have role=reviewer at assign time '
                            '(enforced by reviewer_assigner.assign_reviewers).'
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='review_assignments',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Review assignment',
                'verbose_name_plural': 'Review assignments',
                'db_table': 'htx_review_assignment',
                'ordering': ['-assigned_at'],
                'indexes': [
                    models.Index(fields=['task_id', 'status'], name='htx_ra_task_status_idx'),
                    models.Index(fields=['reviewer', 'status'], name='htx_ra_rev_status_idx'),
                    models.Index(fields=['trainer_id', '-assigned_at'], name='htx_ra_trainer_idx'),
                    models.Index(fields=['deadline_at'], name='htx_ra_deadline_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(
                        fields=['task_id', 'reviewer'],
                        name='htx_ra_unique_task_reviewer',
                    ),
                ],
            },
        ),
        # -------------------------------------------------------------------
        # Review
        # -------------------------------------------------------------------
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'score',
                    models.IntegerField(
                        help_text='1 (poor) to 5 (excellent). Coerced into range at save time.',
                    ),
                ),
                (
                    'agreement',
                    models.CharField(
                        choices=[
                            ('agree', 'Agree'),
                            ('partial', 'Partial'),
                            ('disagree', 'Disagree'),
                            ('dispute', 'Dispute (escalate)'),
                        ],
                        help_text=(
                            "Reviewer's verdict on whether the trainer's answer is "
                            'correct. Drives the consensus engine.'
                        ),
                        max_length=16,
                    ),
                ),
                (
                    'comment',
                    models.TextField(
                        blank=True,
                        default='',
                        help_text=(
                            'Free-text feedback. Optional. Surfaced to the trainer '
                            'after consensus is sealed.'
                        ),
                    ),
                ),
                (
                    'category_checks',
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text=(
                            'Free-shape JSON for per-category booleans — e.g. '
                            '{"grammar": True, "factual": False, "language_pure": True}.'
                        ),
                    ),
                ),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                (
                    'review_assignment',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='review',
                        to='peer_review.reviewassignment',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Review',
                'verbose_name_plural': 'Reviews',
                'db_table': 'htx_review',
                'ordering': ['-submitted_at'],
                'indexes': [
                    models.Index(fields=['agreement', '-submitted_at'], name='htx_rv_agree_idx'),
                ],
            },
        ),
        # -------------------------------------------------------------------
        # ConsensusResult
        # -------------------------------------------------------------------
        migrations.CreateModel(
            name='ConsensusResult',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'task_id',
                    models.IntegerField(
                        help_text='Loose FK-by-value to tasks.Task. One consensus row per task.',
                        unique=True,
                    ),
                ),
                (
                    'total_reviewers',
                    models.PositiveSmallIntegerField(
                        default=3,
                        help_text=(
                            'Number of reviewers expected. Always 3 in Phase 1; future '
                            'tiers may scale this (golden-task spot-checks etc.).'
                        ),
                    ),
                ),
                (
                    'agreed_count',
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text='Reviewers who voted "agree". Drives the status bucket.',
                    ),
                ),
                (
                    'disagree_count',
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text='Reviewers who voted "disagree" or "dispute".',
                    ),
                ),
                (
                    'partial_count',
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text='Reviewers who voted "partial". Counted as half-agreement.',
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('approved', 'Approved (3/3 agree)'),
                            ('flagged', 'Flagged (2/3 agree — spot-check)'),
                            ('dispute', 'Dispute (1/3 agree — QA escalate)'),
                            ('rejected', 'Rejected (0/3 agree)'),
                        ],
                        max_length=16,
                    ),
                ),
                ('computed_at', models.DateTimeField(auto_now_add=True)),
                (
                    'fallback_used',
                    models.BooleanField(
                        default=False,
                        help_text='True when the 48h timeout fell back to fewer than 3 reviewers.',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Consensus result',
                'verbose_name_plural': 'Consensus results',
                'db_table': 'htx_consensus_result',
                'ordering': ['-computed_at'],
                'indexes': [
                    models.Index(fields=['status', '-computed_at'], name='htx_cr_status_idx'),
                ],
            },
        ),
        # -------------------------------------------------------------------
        # Dispute
        # -------------------------------------------------------------------
        migrations.CreateModel(
            name='Dispute',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('escalated_at', models.DateTimeField(auto_now_add=True)),
                (
                    'qa_decision',
                    models.TextField(
                        blank=True,
                        default='',
                        help_text=(
                            "Short summary of the QA lead's decision (free-text). "
                            'Distinct from `qa_notes` which is the longer rationale.'
                        ),
                    ),
                ),
                (
                    'qa_notes',
                    models.TextField(
                        blank=True,
                        default='',
                        help_text=(
                            'Free-text rationale shown to the trainer + reviewers '
                            'after resolution.'
                        ),
                    ),
                ),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                (
                    'resolution',
                    models.CharField(
                        blank=True,
                        choices=[
                            ('trainer_correct', 'Trainer correct'),
                            ('reviewer_correct', 'Reviewer majority correct'),
                            ('ml_recheck', 'Send to ML re-check'),
                            ('inconclusive', 'Inconclusive'),
                        ],
                        default='',
                        help_text=(
                            'One of trainer_correct, reviewer_correct, ml_recheck, '
                            'inconclusive. Empty while pending.'
                        ),
                        max_length=24,
                    ),
                ),
                (
                    'consensus_result',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='dispute',
                        to='peer_review.consensusresult',
                    ),
                ),
                (
                    'qa_lead',
                    models.ForeignKey(
                        blank=True,
                        help_text='The QA lead who resolved the dispute. Null while pending.',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='disputes_handled',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Dispute',
                'verbose_name_plural': 'Disputes',
                'db_table': 'htx_dispute',
                'ordering': ['-escalated_at'],
                'indexes': [
                    models.Index(fields=['resolution', '-escalated_at'], name='htx_dp_res_idx'),
                    models.Index(fields=['qa_lead', '-escalated_at'], name='htx_dp_qa_idx'),
                ],
            },
        ),
    ]
