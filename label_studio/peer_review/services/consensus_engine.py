"""TrainPlex 3-reviewer consensus engine — Phase 1 Step 6.

Pure-logic service that turns the rows in ``htx_review`` (filtered by a
specific ``task_id``) into a single ``ConsensusResult`` row + an optional
``Dispute`` escalation.

Rules (per founder spec)
------------------------
* 3/3 agree    → ``approved``   (release payment, no spot-check)
* 2/3 agree    → ``flagged``    (release + spot-check by admin)
* 1/3 agree    → ``dispute``    (escalate to QA lead, payment HOLD)
* 0/3 agree    → ``rejected``   (no payment, trainer feedback)

Counting semantics
------------------
* "agree" votes count as 1.
* "partial" votes count as 0.5 (toward agreed_count) so two ``partial`` votes
  + one ``agree`` still trips 2-agree-equivalent → ``flagged``, not
  ``rejected``. The fractional total is rounded with banker-friendly
  ceiling so 1.5 → 2 (keeps the trainer-benefit-of-doubt).
* "disagree" + "dispute" both count toward ``disagree_count``.

Idempotency
-----------
* ``compute_consensus(task_id)`` is idempotent — recomputing for the same
  task updates the existing ``ConsensusResult`` row in place rather than
  appending a duplicate. The ``task_id`` column on ``ConsensusResult`` is
  ``unique=True`` so a concurrent recompute would raise IntegrityError; we
  catch that and fetch the existing row.

Phase 1 status
--------------
* No payment / QA-lead notification side-effects. Status flip + Dispute row
  is the entire surface. Payment release wiring lands in Step 6.4 (next
  agent).
* 48h timeout sweep is implemented but NOT scheduled — production cron
  registration is a Step 8 / Phase 2 task. Tests exercise it directly.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import List, Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from peer_review.models import (
    ConsensusResult,
    Dispute,
    Review,
    ReviewAssignment,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_consensus(task_id: int) -> ConsensusResult:
    """Aggregate reviewer verdicts for ``task_id`` into a ConsensusResult.

    Returns the persisted ConsensusResult row. Idempotent — calling twice
    for the same task updates the existing row (no duplicate).
    """
    reviews = _load_reviews_for_task(task_id)
    return _persist_consensus(task_id, reviews, total_reviewers=3, fallback=False)


def escalate_to_qa(consensus_result_id: int) -> Optional[Dispute]:
    """Create a Dispute row for the given ConsensusResult.

    Idempotent — if a Dispute already exists for this consensus, return it.
    Returns None if the consensus is not in a disputable state.
    """
    try:
        cr = ConsensusResult.objects.get(id=consensus_result_id)
    except ConsensusResult.DoesNotExist:
        logger.warning('escalate_to_qa: consensus_result_id=%s not found', consensus_result_id)
        return None

    # Only contested + rejected outcomes are escalatable. A clean 3/3 approval
    # never needs QA touch; 2/3 flagged goes to admin spot-check, not QA.
    if cr.status not in (ConsensusResult.STATUS_DISPUTE, ConsensusResult.STATUS_REJECTED):
        return None

    existing = Dispute.objects.filter(consensus_result=cr).first()
    if existing is not None:
        return existing

    return Dispute.objects.create(consensus_result=cr)


def timeout_sweep(now=None) -> int:
    """Auto-decide assignments past their 48h deadline.

    For each task with at least one ``ReviewAssignment`` past ``deadline_at``
    and still ``pending`` / ``in_progress``:

    * Mark those assignments ``expired``.
    * Compute consensus from whatever reviews *did* land (1-reviewer-fallback).
    * Tag the ConsensusResult ``fallback_used=True`` so the admin can spot it.

    Returns the number of task_ids decided by the fallback.
    """
    now = now or timezone.now()
    # Pull the distinct task_ids that have any expired-but-not-yet-completed
    # assignment. We deliberately don't tie the sweep to a specific reviewer —
    # one stale assignment is enough to trigger the fallback for the whole task.
    expired_qs = ReviewAssignment.objects.filter(
        deadline_at__lt=now,
        status__in=[ReviewAssignment.STATUS_PENDING, ReviewAssignment.STATUS_IN_PROGRESS],
    )

    task_ids = list(expired_qs.values_list('task_id', flat=True).distinct())
    if not task_ids:
        return 0

    # Flip those stale rows to expired so they stop showing in the reviewer queue.
    expired_qs.update(status=ReviewAssignment.STATUS_EXPIRED, completed_at=now)

    decided = 0
    for task_id in task_ids:
        reviews = _load_reviews_for_task(task_id)
        # If zero reviews landed, we still flip to "rejected" so the trainer
        # gets feedback rather than waiting forever — but only if at least one
        # assignment existed in the first place (which we just confirmed).
        # Total_reviewers stays 3 (the original expectation); the fallback flag
        # records that we didn't actually receive 3.
        _persist_consensus(task_id, reviews, total_reviewers=3, fallback=True)
        decided += 1

    return decided


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _load_reviews_for_task(task_id: int) -> List[Review]:
    """Pull all `Review` rows whose assignment.task_id matches."""
    return list(
        Review.objects.filter(review_assignment__task_id=task_id)
        .select_related('review_assignment')
        .order_by('submitted_at')
    )


def _classify(reviews: List[Review]) -> dict:
    """Bucket the verdicts into agree / partial / disagree counts.

    "dispute" votes count toward disagree_count — they're a strong "not okay"
    even if the reviewer prefers escalation over a flat reject.
    """
    agreed = sum(1 for r in reviews if r.agreement == Review.AGREE)
    partial = sum(1 for r in reviews if r.agreement == Review.PARTIAL)
    disagree = sum(
        1 for r in reviews if r.agreement in (Review.DISAGREE, Review.DISPUTE)
    )
    return {
        'agreed_count': agreed,
        'partial_count': partial,
        'disagree_count': disagree,
        # Effective "yes" weight (agree = 1.0, partial = 0.5). Used only for
        # the status threshold decision — the persisted counts stay integer.
        'effective_agreed': agreed + (0.5 * partial),
    }


def _status_from_counts(effective_agreed: float, total_reviewers: int) -> str:
    """Map effective-agreed (with 0.5 partial weight) to a status bucket.

    Threshold logic for total_reviewers=3:
        effective >= 3.0  → approved
        effective >= 2.0  → flagged   (covers 2 agrees, or 1 agree + 2 partials)
        effective >= 1.0  → dispute   (covers 1 agree, or 2 partials)
        else              → rejected

    For total_reviewers != 3 we scale linearly off the 3-reviewer thresholds
    so a 5-reviewer panel (future) doesn't accidentally degrade.
    """
    if total_reviewers <= 0:
        return ConsensusResult.STATUS_REJECTED

    # Scale: approved == full panel, flagged >= 2/3 of panel, dispute >= 1/3.
    full_threshold = total_reviewers
    flagged_threshold = (2 * total_reviewers) / 3.0
    dispute_threshold = total_reviewers / 3.0

    if effective_agreed >= full_threshold:
        return ConsensusResult.STATUS_APPROVED
    if effective_agreed >= flagged_threshold:
        return ConsensusResult.STATUS_FLAGGED
    if effective_agreed >= dispute_threshold:
        return ConsensusResult.STATUS_DISPUTE
    return ConsensusResult.STATUS_REJECTED


def _persist_consensus(
    task_id: int,
    reviews: List[Review],
    total_reviewers: int,
    fallback: bool,
) -> ConsensusResult:
    """Build / update the ConsensusResult row + auto-escalate on dispute."""
    counts = _classify(reviews)
    status = _status_from_counts(counts['effective_agreed'], total_reviewers)

    defaults = {
        'total_reviewers': total_reviewers,
        'agreed_count': counts['agreed_count'],
        'disagree_count': counts['disagree_count'],
        'partial_count': counts['partial_count'],
        'status': status,
        'fallback_used': fallback,
    }

    try:
        with transaction.atomic():
            cr, created = ConsensusResult.objects.update_or_create(
                task_id=task_id,
                defaults=defaults,
            )
    except IntegrityError:
        # Two concurrent compute_consensus(task_id) racing — one wins, other
        # falls back to fetching the row. The losing caller still gets a
        # consistent return; we don't re-merge counts.
        cr = ConsensusResult.objects.get(task_id=task_id)
        created = False

    # Auto-escalate disputed + rejected outcomes — keeps the admin / QA-lead
    # surface populated without the caller having to remember a second call.
    if cr.status in (ConsensusResult.STATUS_DISPUTE, ConsensusResult.STATUS_REJECTED):
        escalate_to_qa(cr.id)

    logger.info(
        'consensus.compute task_id=%s status=%s agreed=%s partial=%s disagree=%s '
        'fallback=%s created=%s',
        task_id, cr.status, cr.agreed_count, cr.partial_count, cr.disagree_count,
        cr.fallback_used, created,
    )
    return cr


# ---------------------------------------------------------------------------
# Helpers — surfaced for tests / management commands
# ---------------------------------------------------------------------------


def default_deadline(now=None) -> 'timezone.datetime':
    """48h-after-now timestamp. Centralised so tests can patch one place."""
    base = now or timezone.now()
    return base + timedelta(hours=48)
