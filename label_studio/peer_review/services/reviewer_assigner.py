"""TrainPlex reviewer-assigner — Phase 1 Step 6.

Selects 3 reviewers for a freshly-submitted task. Phase 1 ships the MVP
selection (filter by role=reviewer, exclude the trainer themselves, enforce
cooldown, balance workload by current open assignments). The full algorithm
(tier match / language match / quality boost) is documented inline as TODO
for Phase 2 because the User model doesn't carry tier / language fields
yet — those land with the trainer-profile schema in Step 8.

Cooldown rule (founder spec)
----------------------------
A reviewer must NOT review the same trainer twice within a 7-day rolling
window. ``is_pair_in_cooldown(reviewer_id, trainer_id)`` is the predicate;
``assign_reviewers`` filters by it before picking.

Idempotency
-----------
* ``assign_reviewers(task_id, trainer_id, count=3)`` is idempotent — if
  ``count`` assignments already exist for the task, the call is a no-op
  and returns the existing rows. The unique constraint on
  (task_id, reviewer) is the hard guard.
* Reviewer-pool deficit (fewer than ``count`` candidates) returns whatever
  subset we could pick + logs a warning. The consensus engine's
  ``total_reviewers`` field will still be 3, so a downstream timeout sweep
  is what closes the loop.

Function reference
------------------
* :func:`assign_reviewers(task_id, trainer_id, count=3, language=None,
  trainer_tier=None, now=None) -> list[ReviewAssignment]`
* :func:`is_pair_in_cooldown(reviewer_id, trainer_id, days=7, now=None) -> bool`
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import List, Optional

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from peer_review.models import ReviewAssignment
from peer_review.services.consensus_engine import default_deadline

logger = logging.getLogger(__name__)

User = get_user_model()


# 7-day rolling cooldown — founder spec. Same (reviewer, trainer) pair should
# not appear in this window so reviewer-trainer collusion has a moving target.
DEFAULT_COOLDOWN_DAYS = 7

# Tier ranking — used by the (future) tier-match filter. Higher number =
# higher tier. Trainer's own tier must be strictly lower than reviewer's.
_TIER_RANK = {
    'bronze': 1,
    'silver': 2,
    'gold': 3,
    'platinum': 4,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_pair_in_cooldown(
    reviewer_id: int,
    trainer_id: int,
    days: int = DEFAULT_COOLDOWN_DAYS,
    now=None,
) -> bool:
    """Return True if ``reviewer`` has reviewed ``trainer`` within ``days``."""
    if not reviewer_id or not trainer_id:
        return False
    now = now or timezone.now()
    window_start = now - timedelta(days=days)
    return ReviewAssignment.objects.filter(
        reviewer_id=reviewer_id,
        trainer_id=trainer_id,
        assigned_at__gte=window_start,
    ).exists()


def assign_reviewers(
    task_id: int,
    trainer_id: int,
    count: int = 3,
    language: Optional[str] = None,
    trainer_tier: Optional[str] = None,
    now=None,
) -> List[ReviewAssignment]:
    """Pick + persist ``count`` ReviewAssignment rows for the given task.

    Filters applied (in order):
    1. ``role == 'reviewer'`` (hard requirement).
    2. ``is_active == True``.
    3. Exclude the trainer themselves (a trainer cannot review their own task).
    4. Cooldown — skip reviewers who reviewed this trainer in the last 7 days.
    5. Tier match (Phase 2) — skip reviewers whose tier <= trainer's.
    6. Language match (Phase 2) — skip reviewers whose ``language`` set
       doesn't overlap with the task's language.
    7. Workload balance — order ascending by the reviewer's current ``pending``
       + ``in_progress`` assignment count.

    Returns the persisted ``ReviewAssignment`` rows (existing rows for the
    task are merged into the return value — idempotent).
    """
    if count <= 0:
        return []

    now = now or timezone.now()
    deadline = default_deadline(now)

    # ------- 0. Short-circuit when we already have `count` assignments -------
    existing = list(
        ReviewAssignment.objects.filter(task_id=task_id).select_related('reviewer')
    )
    if len(existing) >= count:
        return existing
    needed = count - len(existing)
    existing_reviewer_ids = {row.reviewer_id for row in existing}

    # ------- 1-3. Hard filters: role, active, not the trainer themselves -----
    qs = User.objects.filter(role='reviewer', is_active=True)
    if trainer_id:
        qs = qs.exclude(id=trainer_id)
    if existing_reviewer_ids:
        qs = qs.exclude(id__in=existing_reviewer_ids)

    # ------- 4. Cooldown -----------------------------------------------------
    # Exclude reviewers who reviewed this trainer in the last 7d via a
    # NOT-IN subquery (cheaper than per-row predicates).
    window_start = now - timedelta(days=DEFAULT_COOLDOWN_DAYS)
    recent_reviewer_ids = ReviewAssignment.objects.filter(
        trainer_id=trainer_id,
        assigned_at__gte=window_start,
    ).values_list('reviewer_id', flat=True)
    qs = qs.exclude(id__in=list(recent_reviewer_ids))

    # ------- 5. Tier match (Phase 2 — User has no `tier` column yet) -------
    # When the trainer-profile schema lands, the User model will gain a
    # `tier` column and the bronze/silver/gold/platinum lookup will become a
    # real filter. Until then we accept the trainer_tier kwarg for forward
    # compatibility and the rest of the algorithm stays the same.
    # TODO Phase 2 Step 8 — replace this stub:
    #   if trainer_tier:
    #       min_required = _TIER_RANK.get(trainer_tier, 0) + 1
    #       qs = qs.filter(tier__in=[
    #           t for t, rank in _TIER_RANK.items() if rank >= min_required
    #       ])

    # ------- 6. Language match (Phase 2 — User has no `language` col yet) ---
    # TODO Phase 2 Step 8 — replace this stub:
    #   if language:
    #       qs = qs.filter(languages__contains=[language])

    # ------- 7. Workload-balance order — fewest open assignments first -----
    qs = qs.annotate(
        open_count=Count(
            'review_assignments',
            filter=Q(
                review_assignments__status__in=[
                    ReviewAssignment.STATUS_PENDING,
                    ReviewAssignment.STATUS_IN_PROGRESS,
                ]
            ),
        )
    ).order_by('open_count', 'id')

    # Pull a small overhead so a unique-constraint race still leaves us 3
    # candidates (e.g. another assignment for the same (task, reviewer) racing).
    candidates = list(qs[: needed + 5])

    if len(candidates) < needed:
        logger.warning(
            'assign_reviewers: only %s candidates available for task_id=%s '
            '(needed %s)',
            len(candidates), task_id, needed,
        )

    created: List[ReviewAssignment] = []
    for cand in candidates:
        if len(created) >= needed:
            break
        try:
            with transaction.atomic():
                row = ReviewAssignment.objects.create(
                    task_id=task_id,
                    trainer_id=trainer_id,
                    reviewer=cand,
                    assigned_at=now,
                    deadline_at=deadline,
                    status=ReviewAssignment.STATUS_PENDING,
                )
                created.append(row)
        except IntegrityError:
            # Race: another caller assigned this (task, reviewer) pair just now.
            # Skip and try the next candidate — final list still has up to
            # `needed` distinct assignments.
            logger.info(
                'assign_reviewers: race on task_id=%s reviewer_id=%s — skipping',
                task_id, cand.id,
            )

    return existing + created
