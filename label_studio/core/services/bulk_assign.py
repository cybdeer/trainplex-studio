"""TrainPlex Bulk Task Assign service — Phase 1 Step 4.2-3.

Founder requirement: "State / tier / language / cert pe filter → ek baar me
100 trainers ko tasks assign. Manual ek-ek checkbox khatam."

This module owns the business logic the admin views delegate to:

* :func:`filter_trainers` — apply state / tier / language / cert filters over
  the trainer roster and return the matching rows with their current active
  task counts.
* :func:`plan_bulk_assignment` — compute how many tasks each trainer will
  receive given the chosen `distribute_strategy` (Phase 1: 'even' /
  'tier-weighted'). Returns a per-trainer plan; the real task creation /
  ProjectMember linkage lives behind a TODO so we can swap to the real
  LS task tables in Phase 2.

Phase 1 caveats
---------------
* Trainer profile fields (state / tier / language / cert_passed) do NOT
  exist on `users.User` yet — the migration that lands them is Phase 2
  Step 8. Until then this service uses a deterministic in-memory roster
  ``_TRAINER_ROSTER`` matching the frontend `MOCK_TRAINERS` in
  ``web/.../ProjectWizard/Step3_Assign.tsx`` so the admin UI is exercise-
  able end-to-end without churn-prone schema changes.
* Tasks-per-trainer is logged + returned but NOT actually written to the
  LS ``tasks_task`` table in Phase 1. The function signature is the
  stable swap-in point for Phase 2 (see
  ``_TODO_PHASE_2_assign_real_tasks``).

Public surface
--------------
* :func:`filter_trainers(state, tier, language, cert_passed)` → list[dict]
* :func:`plan_bulk_assignment(project_id, trainer_ids, tasks_per_trainer,
    strategy)` → dict
* :data:`RATE_LIMIT_BULK_ASSIGN_PER_HOUR` — 5 bulk-assigns / hr / admin
* :data:`DISTRIBUTE_STRATEGIES` — ('even', 'tier-weighted')
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

# Per founder rule + plan: 5 bulk-assign bursts / hour / admin so an
# overzealous admin (or a bug) can't blast the entire roster with
# task allocations on repeat.
RATE_LIMIT_BULK_ASSIGN_PER_HOUR = 5

# Phase 1 strategies. Both are mock-friendly:
#   * 'even'           — every selected trainer gets `tasks_per_trainer`.
#   * 'tier-weighted'  — higher tier gets MORE tasks
#                        (platinum = x2.0, gold = x1.5, silver = x1.0,
#                         bronze = x0.5 rounded). Mirrors how the founder
#                        team verbally describes "Gold ko zyada milega".
DISTRIBUTE_STRATEGIES = ('even', 'tier-weighted')

# Tier weight table for 'tier-weighted'. Bronze gets less so new trainers
# aren't drowned; platinum gets the most because the founder team has the
# highest confidence in them. These numbers are intentionally simple so the
# distribution is auditable from the response alone.
_TIER_WEIGHTS: Dict[str, float] = {
    'platinum': 2.0,
    'gold': 1.5,
    'silver': 1.0,
    'bronze': 0.5,
}

# Default tasks per trainer when the admin doesn't override.
DEFAULT_TASKS_PER_TRAINER = 10


# ---------------------------------------------------------------------------
# In-memory roster — matches frontend MOCK_TRAINERS so end-to-end behaviour
# is deterministic across UI + API. Each trainer's id matches the User PK
# the test setUp uses (5, 7, 12, ...). When the real trainer-profile fields
# land on `users.User` in Phase 2, swap this for a real Django queryset
# (see :func:`_TODO_PHASE_2_load_real_trainers`).
#
# Fields:
#   id, name, state, tier, language (single — multi-lang is in `languages`
#   list but the filter uses single-language overlap), languages, cert_passed,
#   current_active_tasks_count.
# ---------------------------------------------------------------------------

_TRAINER_ROSTER: List[Dict[str, Any]] = [
    {'id': 5, 'name': 'Geeta P.', 'state': 'Rajasthan', 'tier': 'gold',
     'languages': ['Hindi'], 'cert_passed': True, 'current_active_tasks_count': 8},
    {'id': 7, 'name': 'Sunil M.', 'state': 'UP', 'tier': 'silver',
     'languages': ['Hindi'], 'cert_passed': True, 'current_active_tasks_count': 12},
    {'id': 12, 'name': 'Anil K.', 'state': 'Bihar', 'tier': 'bronze',
     'languages': ['Hindi'], 'cert_passed': False, 'current_active_tasks_count': 3},
    {'id': 19, 'name': 'Rekha S.', 'state': 'MP', 'tier': 'gold',
     'languages': ['Hindi'], 'cert_passed': True, 'current_active_tasks_count': 6},
    {'id': 23, 'name': 'Vikas T.', 'state': 'Haryana', 'tier': 'silver',
     'languages': ['Hindi', 'Punjabi'], 'cert_passed': True, 'current_active_tasks_count': 9},
    {'id': 31, 'name': 'Priya N.', 'state': 'Maharashtra', 'tier': 'platinum',
     'languages': ['Marathi', 'Hindi'], 'cert_passed': True, 'current_active_tasks_count': 15},
    {'id': 42, 'name': 'Karthik R.', 'state': 'Tamil Nadu', 'tier': 'gold',
     'languages': ['Tamil'], 'cert_passed': True, 'current_active_tasks_count': 7},
    {'id': 47, 'name': 'Lakshmi V.', 'state': 'Telangana', 'tier': 'silver',
     'languages': ['Telugu'], 'cert_passed': False, 'current_active_tasks_count': 4},
    {'id': 51, 'name': 'Amitabh G.', 'state': 'Gujarat', 'tier': 'bronze',
     'languages': ['Gujarati', 'Hindi'], 'cert_passed': True, 'current_active_tasks_count': 2},
    {'id': 58, 'name': 'Sneha M.', 'state': 'Punjab', 'tier': 'gold',
     'languages': ['Punjabi', 'Hindi'], 'cert_passed': True, 'current_active_tasks_count': 10},
    {'id': 63, 'name': 'Raju D.', 'state': 'Karnataka', 'tier': 'silver',
     'languages': ['Hindi'], 'cert_passed': False, 'current_active_tasks_count': 5},
    {'id': 71, 'name': 'Mita B.', 'state': 'West Bengal', 'tier': 'bronze',
     'languages': ['Bengali'], 'cert_passed': True, 'current_active_tasks_count': 1},
]


def _normalise_csv(raw: Optional[str]) -> List[str]:
    """Split a `a,b,c` query param into a clean list. Empty/None → []."""
    if not raw:
        return []
    return [chunk.strip() for chunk in raw.split(',') if chunk.strip()]


def _normalise_cert(values: Sequence[str]) -> Optional[bool]:
    """Coerce a cert filter list to a tri-state.

    Cases
    -----
    * Empty list → None (no filter).
    * Only 'true' or 'passed' → True.
    * Only 'false' or 'pending' → False.
    * Both → None (filter cancels out, return all).
    """
    if not values:
        return None
    truthy = {'true', 'passed', '1', 'yes'}
    falsy = {'false', 'pending', '0', 'no'}
    has_true = any(v.lower() in truthy for v in values)
    has_false = any(v.lower() in falsy for v in values)
    if has_true and not has_false:
        return True
    if has_false and not has_true:
        return False
    return None


# ---------------------------------------------------------------------------
# Filter — Phase 1 (in-memory roster)
# ---------------------------------------------------------------------------


def filter_trainers(
    state: Optional[str] = None,
    tier: Optional[str] = None,
    language: Optional[str] = None,
    cert_passed: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return the trainers matching the given filters.

    Parameters
    ----------
    state, tier, language : str | None
        Comma-separated query strings (e.g. ``"Rajasthan,UP"``). Empty /
        missing means "no filter on this field". Multiple values within
        one field are OR-combined; different fields are AND-combined.
    cert_passed : str | None
        Tri-state filter — see :func:`_normalise_cert`.

    Returns
    -------
    list[dict]
        One dict per matching trainer, each carrying
        ``{id, name, state, tier, language, languages, cert_passed,
        current_active_tasks_count}``. The flat ``language`` field is
        the trainer's primary (first) language for table display; the
        ``languages`` list is the full set for the filter side.
    """
    states = set(_normalise_csv(state))
    tiers = set(_normalise_csv(tier))
    languages = set(_normalise_csv(language))
    cert_filter = _normalise_cert(_normalise_csv(cert_passed))

    out: List[Dict[str, Any]] = []
    for row in _TRAINER_ROSTER:
        if states and row['state'] not in states:
            continue
        if tiers and row['tier'] not in tiers:
            continue
        if languages and not any(l in languages for l in row['languages']):
            continue
        if cert_filter is not None and bool(row['cert_passed']) != cert_filter:
            continue
        out.append(
            {
                'id': row['id'],
                'name': row['name'],
                'state': row['state'],
                'tier': row['tier'],
                'language': row['languages'][0] if row['languages'] else '',
                'languages': list(row['languages']),
                'cert_passed': bool(row['cert_passed']),
                'current_active_tasks_count': int(row['current_active_tasks_count']),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Plan — compute per-trainer task counts for the selected distribution
# ---------------------------------------------------------------------------


def _roster_by_id() -> Dict[int, Dict[str, Any]]:
    return {row['id']: row for row in _TRAINER_ROSTER}


def _weight_for_tier(tier: str) -> float:
    return _TIER_WEIGHTS.get(tier, 1.0)


def plan_bulk_assignment(
    project_id: int,
    trainer_ids: Iterable[int],
    tasks_per_trainer: int = DEFAULT_TASKS_PER_TRAINER,
    strategy: str = 'even',
    *,
    admin_user=None,
) -> Dict[str, Any]:
    """Compute the per-trainer task assignment plan.

    Phase 1: this is MOCK — the plan is computed and logged, but no real
    ``tasks_task`` rows are created. Phase 2 replaces
    :func:`_TODO_PHASE_2_assign_real_tasks` with the real LS write.

    Parameters
    ----------
    project_id : int
        Validated by the caller — exists in the DB.
    trainer_ids : iterable[int]
        Trainer user PKs (validated by the caller — already coerced to ints
        and de-duped). Empty list is invalid; the caller surfaces the 400.
    tasks_per_trainer : int
        Baseline tasks per trainer. With 'tier-weighted' this scales by the
        tier weight (rounded to nearest int, floor 0).
    strategy : str
        One of :data:`DISTRIBUTE_STRATEGIES`. Anything else falls back to
        'even' (logged) so a stale frontend never wedges the founder.
    admin_user : User
        The admin requesting the assignment — logged in the response only.

    Returns
    -------
    dict
        ``{'project_id', 'strategy', 'tasks_per_trainer', 'plan': [...],
        'totals': {'trainers', 'tasks'}}``
        where each entry in ``plan`` is
        ``{'trainer_id', 'name', 'tier', 'will_assign',
        'current_active_tasks_count'}``.
    """
    ids: List[int] = [int(x) for x in (trainer_ids or [])]
    if not ids:
        # Defensive — caller validates first, but keep the invariant local.
        raise ValueError('trainer_ids must be a non-empty list')

    strategy_norm = strategy if strategy in DISTRIBUTE_STRATEGIES else 'even'
    if strategy_norm != strategy:
        logger.info(
            'Bulk assign: unknown strategy %r, falling back to even.', strategy
        )

    by_id = _roster_by_id()
    plan: List[Dict[str, Any]] = []
    total_tasks = 0

    for tid in ids:
        row = by_id.get(tid)
        if row is None:
            # Unknown trainer id — record a 0-task line so the admin sees
            # which ids were ignored. Plan-only, no exception.
            plan.append(
                {
                    'trainer_id': tid,
                    'name': '',
                    'tier': '',
                    'state': '',
                    'language': '',
                    'will_assign': 0,
                    'current_active_tasks_count': 0,
                    'unknown': True,
                }
            )
            continue
        if strategy_norm == 'tier-weighted':
            count = max(0, int(round(tasks_per_trainer * _weight_for_tier(row['tier']))))
        else:
            count = max(0, int(tasks_per_trainer))
        total_tasks += count
        plan.append(
            {
                'trainer_id': tid,
                'name': row['name'],
                'tier': row['tier'],
                'state': row['state'],
                'language': row['languages'][0] if row['languages'] else '',
                'will_assign': count,
                'current_active_tasks_count': int(row['current_active_tasks_count']),
                'unknown': False,
            }
        )

    _TODO_PHASE_2_assign_real_tasks(
        project_id=project_id,
        plan=plan,
        admin_user=admin_user,
    )

    return {
        'project_id': project_id,
        'strategy': strategy_norm,
        'tasks_per_trainer': int(tasks_per_trainer),
        'plan': plan,
        'totals': {
            'trainers': len([p for p in plan if not p['unknown']]),
            'tasks': total_tasks,
        },
    }


def _TODO_PHASE_2_assign_real_tasks(
    project_id: int,
    plan: List[Dict[str, Any]],
    admin_user=None,
) -> None:
    """Phase 1 stub. Phase 2 wires real ``Task`` row creation.

    Logs the planned assignment so the founder can see in container logs
    that the admin request was received but the LS write is deferred.
    """
    logger.info(
        'Bulk assign mock: admin=%s project_id=%s plan=%s '
        '(LS task-table wiring deferred to Phase 2 Step 8).',
        getattr(admin_user, 'email', None),
        project_id,
        [{'trainer_id': p['trainer_id'], 'will_assign': p['will_assign']} for p in plan],
    )


# ---------------------------------------------------------------------------
# Rate limit — 5 bulk-assigns / hour / admin
# ---------------------------------------------------------------------------

# Cheap in-memory bucket. Same pattern as WA broadcast in Phase 1 — when
# bulk-assign gets a persistent log table in Phase 2 this swaps for a DB
# count just like ``admin_recent_broadcast_count``.
_ADMIN_RECENT_ASSIGNS: Dict[int, List[Any]] = {}


def _prune_admin_assigns(admin_user, *, hours: int = 1) -> List[Any]:
    """Drop timestamps older than `hours` from the in-memory bucket."""
    bucket = _ADMIN_RECENT_ASSIGNS.setdefault(getattr(admin_user, 'id', 0), [])
    cutoff = timezone.now() - timedelta(hours=hours)
    bucket[:] = [ts for ts in bucket if ts >= cutoff]
    return bucket


def admin_has_room_for_bulk_assign(admin_user) -> bool:
    """True iff the admin can fire another bulk-assign under the 5/hr cap."""
    if admin_user is None:
        return True
    bucket = _prune_admin_assigns(admin_user)
    return len(bucket) < RATE_LIMIT_BULK_ASSIGN_PER_HOUR


def record_bulk_assign(admin_user) -> None:
    """Mark a successful bulk-assign burst against this admin's bucket."""
    if admin_user is None:
        return
    bucket = _prune_admin_assigns(admin_user)
    bucket.append(timezone.now())


def reset_admin_rate_limit_buckets() -> None:
    """Clear the in-memory rate-limit cache.

    Test-only helper — keeps unit tests isolated when multiple admins or
    multiple bursts get fired in the same test run.
    """
    _ADMIN_RECENT_ASSIGNS.clear()
