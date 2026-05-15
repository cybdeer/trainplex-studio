"""Trainer leaderboard service — Phase 1 Step 7.

Builds the ranked-trainer table for the admin Trainer Leaderboard surface.

Phase 1 (Week 7): MOCK data — 30 deterministic trainers spread across states,
tiers, and languages. Real DB aggregation lands in Phase 2 / Step 8.

Public API
----------
``build_leaderboard(period, filters)`` returns the ranked trainer list plus
the Hall of Fame (lifetime + this month).

Filters supported (all optional, applied AND-wise)
    * ``state``         - ISO 3166-2:IN state code (e.g. ``'RJ'``)
    * ``tier``          - ``'bronze' | 'silver' | 'gold'``
    * ``language``      - language code (``'hi'``, ``'ta'``, ...)
    * ``project_type``  - ``'ocr' | 'voice' | 'image' | 'sentiment' | 'moderation'``

Period
    * ``'daily'``       - last 24h tasks + earnings
    * ``'weekly'``      - last 7 days
    * ``'monthly'``     - last 30 days

Period only scales the magnitude; rank ordering stays stable so the UI doesn't
need a separate test fixture per period.

TODO Phase 2: replace with a real ``Submissions.objects.filter(...).aggregate(
Sum, Count).order_by(...)`` against the period window.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# Period scaling factor — multiplies the "monthly" baseline numbers down so the
# magnitudes feel right for the time-window.
_PERIOD_FACTORS: Dict[str, float] = {
    'daily': 1 / 30,
    'weekly': 1 / 4,
    'monthly': 1.0,
}

_VALID_PERIODS = ('daily', 'weekly', 'monthly')
_DEFAULT_PERIOD = 'weekly'

# Allowed filter values — anything outside is silently dropped so the UI
# can't 400 the founder dashboard with a typo.
_VALID_TIERS = {'bronze', 'silver', 'gold'}
_VALID_PROJECT_TYPES = {'ocr', 'voice', 'image', 'sentiment', 'moderation'}


# ---------------------------------------------------------------------------
# Mock trainer roster
# ---------------------------------------------------------------------------


def _trainer_seed() -> List[Dict[str, Any]]:
    """30 deterministic trainers — covers all states / tiers / languages /
    project_types for filter tests.

    monthly_tasks + monthly_earnings_inr are the baseline; period scaling
    happens at query time so the rank ordering is stable across periods.
    """
    return [
        {'trainer_id': 1, 'name': 'Geeta P.', 'state': 'RJ', 'tier': 'gold',
         'language': 'hi', 'project_type': 'ocr',
         'monthly_tasks': 412, 'monthly_earnings_inr': 21_400,
         'quality_score_pct': 96, 'consistency_pct': 92},
        {'trainer_id': 2, 'name': 'Sunil M.', 'state': 'UP', 'tier': 'gold',
         'language': 'hi', 'project_type': 'voice',
         'monthly_tasks': 388, 'monthly_earnings_inr': 19_800,
         'quality_score_pct': 94, 'consistency_pct': 90},
        {'trainer_id': 3, 'name': 'Anil K.', 'state': 'BR', 'tier': 'gold',
         'language': 'bho', 'project_type': 'voice',
         'monthly_tasks': 362, 'monthly_earnings_inr': 18_400,
         'quality_score_pct': 92, 'consistency_pct': 88},
        {'trainer_id': 4, 'name': 'Rekha S.', 'state': 'MP', 'tier': 'silver',
         'language': 'hi', 'project_type': 'sentiment',
         'monthly_tasks': 342, 'monthly_earnings_inr': 16_900,
         'quality_score_pct': 90, 'consistency_pct': 86},
        {'trainer_id': 5, 'name': 'Vikas T.', 'state': 'HR', 'tier': 'silver',
         'language': 'hi', 'project_type': 'image',
         'monthly_tasks': 318, 'monthly_earnings_inr': 15_600,
         'quality_score_pct': 89, 'consistency_pct': 85},
        {'trainer_id': 6, 'name': 'Lakshmi V.', 'state': 'TN', 'tier': 'gold',
         'language': 'ta', 'project_type': 'ocr',
         'monthly_tasks': 308, 'monthly_earnings_inr': 15_200,
         'quality_score_pct': 95, 'consistency_pct': 89},
        {'trainer_id': 7, 'name': 'Rajesh N.', 'state': 'KA', 'tier': 'silver',
         'language': 'kn', 'project_type': 'sentiment',
         'monthly_tasks': 294, 'monthly_earnings_inr': 14_500,
         'quality_score_pct': 88, 'consistency_pct': 84},
        {'trainer_id': 8, 'name': 'Priya R.', 'state': 'MH', 'tier': 'silver',
         'language': 'mr', 'project_type': 'voice',
         'monthly_tasks': 282, 'monthly_earnings_inr': 13_900,
         'quality_score_pct': 87, 'consistency_pct': 83},
        {'trainer_id': 9, 'name': 'Manoj D.', 'state': 'GJ', 'tier': 'silver',
         'language': 'gu', 'project_type': 'ocr',
         'monthly_tasks': 268, 'monthly_earnings_inr': 13_200,
         'quality_score_pct': 86, 'consistency_pct': 82},
        {'trainer_id': 10, 'name': 'Sushma K.', 'state': 'PB', 'tier': 'gold',
         'language': 'pa', 'project_type': 'voice',
         'monthly_tasks': 256, 'monthly_earnings_inr': 12_700,
         'quality_score_pct': 93, 'consistency_pct': 87},
        {'trainer_id': 11, 'name': 'Arvind J.', 'state': 'WB', 'tier': 'silver',
         'language': 'bn', 'project_type': 'sentiment',
         'monthly_tasks': 248, 'monthly_earnings_inr': 12_200,
         'quality_score_pct': 85, 'consistency_pct': 81},
        {'trainer_id': 12, 'name': 'Pooja G.', 'state': 'DL', 'tier': 'silver',
         'language': 'hi', 'project_type': 'moderation',
         'monthly_tasks': 232, 'monthly_earnings_inr': 11_500,
         'quality_score_pct': 86, 'consistency_pct': 80},
        {'trainer_id': 13, 'name': 'Sanjay B.', 'state': 'JH', 'tier': 'silver',
         'language': 'hi', 'project_type': 'image',
         'monthly_tasks': 218, 'monthly_earnings_inr': 10_700,
         'quality_score_pct': 84, 'consistency_pct': 79},
        {'trainer_id': 14, 'name': 'Anita P.', 'state': 'AP', 'tier': 'silver',
         'language': 'te', 'project_type': 'ocr',
         'monthly_tasks': 208, 'monthly_earnings_inr': 10_300,
         'quality_score_pct': 84, 'consistency_pct': 78},
        {'trainer_id': 15, 'name': 'Vinod J.', 'state': 'KL', 'tier': 'bronze',
         'language': 'hi', 'project_type': 'voice',
         'monthly_tasks': 198, 'monthly_earnings_inr': 9_800,
         'quality_score_pct': 82, 'consistency_pct': 76},
        {'trainer_id': 16, 'name': 'Meena S.', 'state': 'TG', 'tier': 'bronze',
         'language': 'te', 'project_type': 'sentiment',
         'monthly_tasks': 188, 'monthly_earnings_inr': 9_200,
         'quality_score_pct': 81, 'consistency_pct': 75},
        {'trainer_id': 17, 'name': 'Hari K.', 'state': 'OR', 'tier': 'bronze',
         'language': 'or', 'project_type': 'ocr',
         'monthly_tasks': 178, 'monthly_earnings_inr': 8_700,
         'quality_score_pct': 80, 'consistency_pct': 74},
        {'trainer_id': 18, 'name': 'Kavita M.', 'state': 'AS', 'tier': 'bronze',
         'language': 'hi', 'project_type': 'voice',
         'monthly_tasks': 168, 'monthly_earnings_inr': 8_300,
         'quality_score_pct': 79, 'consistency_pct': 73},
        {'trainer_id': 19, 'name': 'Rohit P.', 'state': 'RJ', 'tier': 'bronze',
         'language': 'hi', 'project_type': 'image',
         'monthly_tasks': 158, 'monthly_earnings_inr': 7_800,
         'quality_score_pct': 78, 'consistency_pct': 72},
        {'trainer_id': 20, 'name': 'Smita D.', 'state': 'UP', 'tier': 'bronze',
         'language': 'hi', 'project_type': 'sentiment',
         'monthly_tasks': 148, 'monthly_earnings_inr': 7_300,
         'quality_score_pct': 78, 'consistency_pct': 71},
        {'trainer_id': 21, 'name': 'Ramesh K.', 'state': 'MH', 'tier': 'bronze',
         'language': 'mr', 'project_type': 'moderation',
         'monthly_tasks': 138, 'monthly_earnings_inr': 6_800,
         'quality_score_pct': 77, 'consistency_pct': 70},
        {'trainer_id': 22, 'name': 'Sneha A.', 'state': 'KA', 'tier': 'bronze',
         'language': 'kn', 'project_type': 'image',
         'monthly_tasks': 128, 'monthly_earnings_inr': 6_400,
         'quality_score_pct': 77, 'consistency_pct': 69},
        {'trainer_id': 23, 'name': 'Deepak T.', 'state': 'GJ', 'tier': 'bronze',
         'language': 'gu', 'project_type': 'voice',
         'monthly_tasks': 118, 'monthly_earnings_inr': 5_900,
         'quality_score_pct': 76, 'consistency_pct': 68},
        {'trainer_id': 24, 'name': 'Nisha G.', 'state': 'TN', 'tier': 'bronze',
         'language': 'ta', 'project_type': 'sentiment',
         'monthly_tasks': 108, 'monthly_earnings_inr': 5_400,
         'quality_score_pct': 76, 'consistency_pct': 67},
        {'trainer_id': 25, 'name': 'Suresh L.', 'state': 'AP', 'tier': 'bronze',
         'language': 'te', 'project_type': 'ocr',
         'monthly_tasks': 98, 'monthly_earnings_inr': 4_900,
         'quality_score_pct': 75, 'consistency_pct': 66},
        {'trainer_id': 26, 'name': 'Bhavna R.', 'state': 'BR', 'tier': 'bronze',
         'language': 'bho', 'project_type': 'voice',
         'monthly_tasks': 88, 'monthly_earnings_inr': 4_400,
         'quality_score_pct': 75, 'consistency_pct': 65},
        {'trainer_id': 27, 'name': 'Karan S.', 'state': 'PB', 'tier': 'bronze',
         'language': 'pa', 'project_type': 'moderation',
         'monthly_tasks': 78, 'monthly_earnings_inr': 3_900,
         'quality_score_pct': 74, 'consistency_pct': 64},
        {'trainer_id': 28, 'name': 'Asha N.', 'state': 'WB', 'tier': 'bronze',
         'language': 'bn', 'project_type': 'image',
         'monthly_tasks': 68, 'monthly_earnings_inr': 3_400,
         'quality_score_pct': 73, 'consistency_pct': 62},
        {'trainer_id': 29, 'name': 'Mukesh V.', 'state': 'MP', 'tier': 'bronze',
         'language': 'hi', 'project_type': 'sentiment',
         'monthly_tasks': 58, 'monthly_earnings_inr': 2_900,
         'quality_score_pct': 72, 'consistency_pct': 60},
        {'trainer_id': 30, 'name': 'Renu D.', 'state': 'DL', 'tier': 'bronze',
         'language': 'hi', 'project_type': 'ocr',
         'monthly_tasks': 48, 'monthly_earnings_inr': 2_400,
         'quality_score_pct': 71, 'consistency_pct': 58},
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _normalise_period(period: Optional[str]) -> str:
    if not period:
        return _DEFAULT_PERIOD
    p = period.strip().lower()
    return p if p in _VALID_PERIODS else _DEFAULT_PERIOD


def _apply_filters(rows: List[Dict[str, Any]], filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """AND-wise filter. Unknown values are silently dropped (no 400)."""
    if not filters:
        return rows
    state = (filters.get('state') or '').strip().upper() or None
    tier = (filters.get('tier') or '').strip().lower() or None
    language = (filters.get('language') or '').strip().lower() or None
    project_type = (filters.get('project_type') or '').strip().lower() or None
    if tier and tier not in _VALID_TIERS:
        tier = None
    if project_type and project_type not in _VALID_PROJECT_TYPES:
        project_type = None

    out: List[Dict[str, Any]] = []
    for row in rows:
        if state and row['state'] != state:
            continue
        if tier and row['tier'] != tier:
            continue
        if language and row['language'] != language:
            continue
        if project_type and row['project_type'] != project_type:
            continue
        out.append(row)
    return out


def build_leaderboard(
    period: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return the ranked leaderboard payload.

    Returns
    -------
    Dict with keys:
        * ``period``                - normalised period actually used
        * ``filters``                - echo of normalised filters
        * ``results``                - ranked trainer list (rank starts at 1)
        * ``hall_of_fame_lifetime``  - top 10 by lifetime earnings
        * ``hall_of_fame_month``     - top 10 by this-month earnings
        * ``total``                  - count of trainers in ``results``
    """
    p = _normalise_period(period)
    factor = _PERIOD_FACTORS[p]
    rows = _apply_filters(_trainer_seed(), filters)

    # Sort by monthly_tasks DESC (rank by output), tiebreak by quality.
    sorted_rows = sorted(
        rows,
        key=lambda r: (-r['monthly_tasks'], -r['quality_score_pct']),
    )

    results: List[Dict[str, Any]] = []
    for idx, row in enumerate(sorted_rows, start=1):
        scaled_tasks = max(0, int(round(row['monthly_tasks'] * factor)))
        scaled_earnings = max(0, int(round(row['monthly_earnings_inr'] * factor)))
        results.append({
            'rank': idx,
            'trainer_id': row['trainer_id'],
            'name': row['name'],
            'state': row['state'],
            'tier': row['tier'],
            'language': row['language'],
            'project_type': row['project_type'],
            'tasks_done': scaled_tasks,
            'earnings_inr': scaled_earnings,
            'quality_score_pct': row['quality_score_pct'],
            'consistency_pct': row['consistency_pct'],
        })

    # Hall of fame is computed on the UNFILTERED roster so the founder sees
    # the same 10 names regardless of the active filter set.
    all_rows = _trainer_seed()
    lifetime_sorted = sorted(
        all_rows,
        key=lambda r: -(r['monthly_tasks'] * 12),  # 12-month lifetime proxy
    )[:10]
    hall_of_fame_lifetime = [
        {
            'rank': idx + 1,
            'trainer_id': r['trainer_id'],
            'name': r['name'],
            'state': r['state'],
            'lifetime_tasks': r['monthly_tasks'] * 12,
            'lifetime_earnings_inr': r['monthly_earnings_inr'] * 12,
        }
        for idx, r in enumerate(lifetime_sorted)
    ]
    month_sorted = sorted(all_rows, key=lambda r: -r['monthly_tasks'])[:10]
    hall_of_fame_month = [
        {
            'rank': idx + 1,
            'trainer_id': r['trainer_id'],
            'name': r['name'],
            'state': r['state'],
            'tasks_this_month': r['monthly_tasks'],
            'earnings_this_month_inr': r['monthly_earnings_inr'],
        }
        for idx, r in enumerate(month_sorted)
    ]

    return {
        'period': p,
        'filters': {
            'state': (filters or {}).get('state') or None,
            'tier': (filters or {}).get('tier') or None,
            'language': (filters or {}).get('language') or None,
            'project_type': (filters or {}).get('project_type') or None,
        },
        'total': len(results),
        'results': results,
        'hall_of_fame_lifetime': hall_of_fame_lifetime,
        'hall_of_fame_month': hall_of_fame_month,
    }
