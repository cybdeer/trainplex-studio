"""TrainPlex peer-review models — Phase 1 Step 6.

Four tables back the 3-reviewer consensus + dispute flow:

* ``ReviewAssignment`` (``htx_review_assignment``) — one row per (task,
  reviewer) pair. Created by ``services.reviewer_assigner.assign_reviewers``
  when a trainer submits a task. ``deadline_at`` defaults to 48h after
  ``assigned_at``; the timeout sweep auto-decides with the reviewers who DID
  respond.

* ``Review`` (``htx_review``) — the reviewer's verdict against an
  assignment. 1-1 with ``ReviewAssignment``. ``score`` is 1-5,
  ``agreement`` ∈ {agree, partial, disagree, dispute}, ``comment`` free-text,
  ``category_checks`` an arbitrary JSON dict (e.g. ``{"grammar": True,
  "factual": False}``).

* ``ConsensusResult`` (``htx_consensus_result``) — append-once aggregate of
  the 3 reviews for a task. ``status`` ∈ {approved, flagged, dispute,
  rejected}, derived by
  :func:`peer_review.services.consensus_engine.compute_consensus`.

* ``Dispute`` (``htx_dispute``) — escalation row when ConsensusResult lands
  in ``dispute`` or a QA lead manually opens one. Resolution flips
  ``resolved_at`` + ``resolution`` to one of trainer_correct,
  reviewer_correct, ml_recheck, or inconclusive.

Phase 1 status
--------------
* ``task_id`` is stored as a loose integer (no hard FK to ``tasks.Task``) so
  the table can exercise its full lifecycle even on rows that originated
  from a synthetic/mock submission ID — important because peer-review
  Phase 1 ships with mock submission inputs (see
  ``core/services/quality_anomaly_detector.py`` for the same pattern).
* The reviewer-assigner is MOCKED to pick from ``User.role='reviewer'`` —
  the real tier/language/cooldown algorithm lands in Phase 2 (Step 8).
* Payment release wiring is the NEXT agent's job (Step 6.4); this app only
  emits the ``ConsensusResult`` row + status — no Razorpay / payout call.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# ReviewAssignment
# ---------------------------------------------------------------------------


class ReviewAssignment(models.Model):
    """One row per (task, reviewer) — the work item on the reviewer's queue."""

    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_DONE = 'done'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_PROGRESS, 'In progress'),
        (STATUS_DONE, 'Done'),
        (STATUS_EXPIRED, 'Expired (timeout)'),
    ]

    task_id = models.IntegerField(
        help_text=_('Loose FK-by-value to tasks.Task. Phase 1 keeps this a '
                    'plain integer so a synthetic / hard-deleted task does not '
                    'orphan-purge the review trail.'),
    )

    trainer_id = models.IntegerField(
        null=True,
        blank=True,
        help_text=_('Snapshot of the task submitter id for fast queue rendering '
                    'and the cooldown check (same reviewer should not review the '
                    'same trainer within 7 days).'),
    )

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_assignments',
        help_text=_('The reviewer User. Must have role=reviewer at assign time '
                    '(enforced by reviewer_assigner.assign_reviewers).'),
    )

    assigned_at = models.DateTimeField(default=timezone.now)

    deadline_at = models.DateTimeField(
        help_text=_('Auto-set to assigned_at + 48h by reviewer_assigner. '
                    'The timeout sweep flips status to "expired" past this point.'),
    )

    completed_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    class Meta:
        db_table = 'htx_review_assignment'
        verbose_name = _('Review assignment')
        verbose_name_plural = _('Review assignments')
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['task_id', 'status'], name='htx_ra_task_status_idx'),
            models.Index(fields=['reviewer', 'status'], name='htx_ra_rev_status_idx'),
            models.Index(fields=['trainer_id', '-assigned_at'], name='htx_ra_trainer_idx'),
            models.Index(fields=['deadline_at'], name='htx_ra_deadline_idx'),
        ]
        # Same (task, reviewer) should never duplicate — second assign attempt
        # should be a no-op via reviewer_assigner.
        constraints = [
            models.UniqueConstraint(
                fields=['task_id', 'reviewer'],
                name='htx_ra_unique_task_reviewer',
            ),
        ]

    def __str__(self):  # pragma: no cover  (display only)
        return (
            f'ReviewAssignment(id={self.id}, task_id={self.task_id}, '
            f'reviewer_id={self.reviewer_id}, status={self.status})'
        )


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


class Review(models.Model):
    """The reviewer's verdict against an assignment. 1-1 with ReviewAssignment."""

    AGREE = 'agree'
    PARTIAL = 'partial'
    DISAGREE = 'disagree'
    DISPUTE = 'dispute'

    AGREEMENT_CHOICES = [
        (AGREE, 'Agree'),
        (PARTIAL, 'Partial'),
        (DISAGREE, 'Disagree'),
        (DISPUTE, 'Dispute (escalate)'),
    ]

    review_assignment = models.OneToOneField(
        ReviewAssignment,
        on_delete=models.CASCADE,
        related_name='review',
    )

    score = models.IntegerField(
        help_text=_('1 (poor) to 5 (excellent). Coerced into range at save time.'),
    )

    agreement = models.CharField(
        max_length=16,
        choices=AGREEMENT_CHOICES,
        help_text=_('Reviewer\'s verdict on whether the trainer\'s answer is '
                    'correct. Drives the consensus engine.'),
    )

    comment = models.TextField(
        blank=True,
        default='',
        help_text=_('Free-text feedback. Optional. Surfaced to the trainer '
                    'after consensus is sealed.'),
    )

    category_checks = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Free-shape JSON for per-category booleans — e.g. '
                    '{"grammar": True, "factual": False, "language_pure": True}.'),
    )

    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'htx_review'
        verbose_name = _('Review')
        verbose_name_plural = _('Reviews')
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['agreement', '-submitted_at'], name='htx_rv_agree_idx'),
        ]

    def __str__(self):  # pragma: no cover  (display only)
        return (
            f'Review(id={self.id}, assignment_id={self.review_assignment_id}, '
            f'score={self.score}, agreement={self.agreement})'
        )


# ---------------------------------------------------------------------------
# ConsensusResult
# ---------------------------------------------------------------------------


class ConsensusResult(models.Model):
    """Aggregate of the 3 reviewers' verdicts for a single task."""

    STATUS_APPROVED = 'approved'
    STATUS_FLAGGED = 'flagged'
    STATUS_DISPUTE = 'dispute'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_APPROVED, 'Approved (3/3 agree)'),
        (STATUS_FLAGGED, 'Flagged (2/3 agree — spot-check)'),
        (STATUS_DISPUTE, 'Dispute (1/3 agree — QA escalate)'),
        (STATUS_REJECTED, 'Rejected (0/3 agree)'),
    ]

    task_id = models.IntegerField(
        unique=True,
        help_text=_('Loose FK-by-value to tasks.Task. One consensus row per task.'),
    )

    total_reviewers = models.PositiveSmallIntegerField(
        default=3,
        help_text=_('Number of reviewers expected. Always 3 in Phase 1; future '
                    'tiers may scale this (golden-task spot-checks etc.).'),
    )

    agreed_count = models.PositiveSmallIntegerField(
        default=0,
        help_text=_('Reviewers who voted "agree". Drives the status bucket.'),
    )

    disagree_count = models.PositiveSmallIntegerField(
        default=0,
        help_text=_('Reviewers who voted "disagree" or "dispute".'),
    )

    partial_count = models.PositiveSmallIntegerField(
        default=0,
        help_text=_('Reviewers who voted "partial". Counted as half-agreement.'),
    )

    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
    )

    computed_at = models.DateTimeField(auto_now_add=True)

    # 1-reviewer-fallback flag — set when the timeout sweep decided this
    # consensus with fewer than the expected 3 reviews. Stored separately
    # from status so the admin can spot synthetic / partial-panel rows.
    fallback_used = models.BooleanField(
        default=False,
        help_text=_('True when the 48h timeout fell back to fewer than 3 reviewers.'),
    )

    class Meta:
        db_table = 'htx_consensus_result'
        verbose_name = _('Consensus result')
        verbose_name_plural = _('Consensus results')
        ordering = ['-computed_at']
        indexes = [
            models.Index(fields=['status', '-computed_at'], name='htx_cr_status_idx'),
        ]

    def __str__(self):  # pragma: no cover  (display only)
        return (
            f'ConsensusResult(id={self.id}, task_id={self.task_id}, '
            f'status={self.status}, agreed={self.agreed_count}/{self.total_reviewers})'
        )


# ---------------------------------------------------------------------------
# Dispute
# ---------------------------------------------------------------------------


class Dispute(models.Model):
    """QA-lead escalation row for a contested ConsensusResult."""

    RES_TRAINER_CORRECT = 'trainer_correct'
    RES_REVIEWER_CORRECT = 'reviewer_correct'
    RES_ML_RECHECK = 'ml_recheck'
    RES_INCONCLUSIVE = 'inconclusive'

    RESOLUTION_CHOICES = [
        (RES_TRAINER_CORRECT, 'Trainer correct'),
        (RES_REVIEWER_CORRECT, 'Reviewer majority correct'),
        (RES_ML_RECHECK, 'Send to ML re-check'),
        (RES_INCONCLUSIVE, 'Inconclusive'),
    ]

    consensus_result = models.OneToOneField(
        ConsensusResult,
        on_delete=models.CASCADE,
        related_name='dispute',
    )

    escalated_at = models.DateTimeField(auto_now_add=True)

    qa_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='disputes_handled',
        help_text=_('The QA lead who resolved the dispute. Null while pending.'),
    )

    qa_decision = models.TextField(
        blank=True,
        default='',
        help_text=_('Short summary of the QA lead\'s decision (free-text). '
                    'Distinct from `qa_notes` which is the longer rationale.'),
    )

    qa_notes = models.TextField(
        blank=True,
        default='',
        help_text=_('Free-text rationale shown to the trainer + reviewers '
                    'after resolution.'),
    )

    resolved_at = models.DateTimeField(null=True, blank=True)

    resolution = models.CharField(
        max_length=24,
        choices=RESOLUTION_CHOICES,
        blank=True,
        default='',
        help_text=_('One of trainer_correct, reviewer_correct, ml_recheck, '
                    'inconclusive. Empty while pending.'),
    )

    class Meta:
        db_table = 'htx_dispute'
        verbose_name = _('Dispute')
        verbose_name_plural = _('Disputes')
        ordering = ['-escalated_at']
        indexes = [
            models.Index(fields=['resolution', '-escalated_at'], name='htx_dp_res_idx'),
            models.Index(fields=['qa_lead', '-escalated_at'], name='htx_dp_qa_idx'),
        ]

    @property
    def is_resolved(self) -> bool:
        return bool(self.resolved_at and self.resolution)

    def __str__(self):  # pragma: no cover  (display only)
        return (
            f'Dispute(id={self.id}, consensus_id={self.consensus_result_id}, '
            f'resolved={self.is_resolved}, resolution={self.resolution!r})'
        )
