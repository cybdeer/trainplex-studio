"""Cohort retention analyzer — Phase 1 Step 7.

Builds cohort-based curves the founder uses to understand how trainer waves
behave over time.

Cohort definitions
------------------
* ``'registration_week'``   - bucket trainers by ISO week of signup
* ``'signup_wave'``         - bucket trainers by hiring wave (named cohorts)
* ``'tier_promotion_month'``- bucket trainers by the month they were promoted
                              to silver/gold

Curves returned per cohort
--------------------------
* ``retention_curve``     - day 7 / 30 / 60 / 90 retention %
* ``productivity_curve``  - average tasks/day per cohort by week-since-signup
* ``earnings_curve``      - cumulative ₹ per cohort member by week-since-signup
* ``drop_off_analysis``   - per-stage trainer-count fall-off

Phase 1: deterministic mocks. Phase 2 swaps to real ``Trainer.objects``
queries grouped by signup ISO week / wave label / tier promotion month.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


_VALID_COHORT_DEFINITIONS = (
    'registration_week',
    'signup_wave',
    'tier_promotion_month',
)
_DEFAULT_COHORT_DEFINITION = 'signup_wave'


def _retention_curve(day_7: int, day_30: int, day_60: int, day_90: int) -> List[Dict[str, Any]]:
    """4-point retention curve so the React heatmap can render cleanly."""
    return [
        {'day': 7, 'retention_pct': day_7},
        {'day': 30, 'retention_pct': day_30},
        {'day': 60, 'retention_pct': day_60},
        {'day': 90, 'retention_pct': day_90},
    ]


def _productivity_curve(start: int, end: int, weeks: int = 12) -> List[Dict[str, Any]]:
    """Smooth productivity ramp — linear interpolation from start → end."""
    if weeks < 2:
        return [{'week': 1, 'avg_tasks_per_day': start}]
    step = (end - start) / (weeks - 1)
    return [
        {
            'week': w + 1,
            'avg_tasks_per_day': max(0, int(round(start + step * w))),
        }
        for w in range(weeks)
    ]


def _earnings_curve(weekly_inr: int, weeks: int = 12) -> List[Dict[str, Any]]:
    """Cumulative earnings per cohort member, weekly_inr ₹/week."""
    return [
        {
            'week': w + 1,
            'cumulative_earnings_inr': weekly_inr * (w + 1),
        }
        for w in range(weeks)
    ]


def _drop_off(stages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Decorate the drop-off list with a `drop_pct` between consecutive stages."""
    out: List[Dict[str, Any]] = []
    prev: Optional[int] = None
    for stage in stages:
        count = stage['trainers_remaining']
        if prev is None or prev == 0:
            drop_pct = 0
        else:
            drop_pct = int(round((1 - (count / prev)) * 100))
        out.append({**stage, 'drop_pct': drop_pct})
        prev = count
    return out


def _cohort_signup_wave_mock() -> List[Dict[str, Any]]:
    return [
        {
            'cohort_id': 'wave-1-mar-2026',
            'cohort_name': 'Wave 1 (Mar 2026)',
            'cohort_start': '2026-03-04',
            'cohort_size': 42,
            'retention_curve': _retention_curve(88, 74, 62, 55),
            'productivity_curve': _productivity_curve(start=4, end=14),
            'earnings_curve': _earnings_curve(weekly_inr=1_800),
            'drop_off_analysis': _drop_off([
                {'stage': 'signed_up', 'trainers_remaining': 42},
                {'stage': 'completed_kyc', 'trainers_remaining': 38},
                {'stage': 'first_task', 'trainers_remaining': 36},
                {'stage': 'first_payout', 'trainers_remaining': 32},
                {'stage': 'active_30_days', 'trainers_remaining': 28},
                {'stage': 'active_60_days', 'trainers_remaining': 24},
                {'stage': 'active_90_days', 'trainers_remaining': 21},
            ]),
        },
        {
            'cohort_id': 'wave-2-mar-2026',
            'cohort_name': 'Wave 2 (Mar 2026)',
            'cohort_start': '2026-03-25',
            'cohort_size': 38,
            'retention_curve': _retention_curve(84, 71, 60, 52),
            'productivity_curve': _productivity_curve(start=3, end=12),
            'earnings_curve': _earnings_curve(weekly_inr=1_650),
            'drop_off_analysis': _drop_off([
                {'stage': 'signed_up', 'trainers_remaining': 38},
                {'stage': 'completed_kyc', 'trainers_remaining': 33},
                {'stage': 'first_task', 'trainers_remaining': 31},
                {'stage': 'first_payout', 'trainers_remaining': 28},
                {'stage': 'active_30_days', 'trainers_remaining': 24},
                {'stage': 'active_60_days', 'trainers_remaining': 20},
                {'stage': 'active_90_days', 'trainers_remaining': 17},
            ]),
        },
        {
            'cohort_id': 'wave-3-apr-2026',
            'cohort_name': 'Wave 3 (Apr 2026)',
            'cohort_start': '2026-04-08',
            'cohort_size': 56,
            'retention_curve': _retention_curve(91, 79, 66, 58),
            'productivity_curve': _productivity_curve(start=5, end=16),
            'earnings_curve': _earnings_curve(weekly_inr=2_100),
            'drop_off_analysis': _drop_off([
                {'stage': 'signed_up', 'trainers_remaining': 56},
                {'stage': 'completed_kyc', 'trainers_remaining': 53},
                {'stage': 'first_task', 'trainers_remaining': 51},
                {'stage': 'first_payout', 'trainers_remaining': 47},
                {'stage': 'active_30_days', 'trainers_remaining': 44},
                {'stage': 'active_60_days', 'trainers_remaining': 37},
                {'stage': 'active_90_days', 'trainers_remaining': 32},
            ]),
        },
        {
            'cohort_id': 'wave-4-apr-2026',
            'cohort_name': 'Wave 4 (Apr 2026)',
            'cohort_start': '2026-04-29',
            'cohort_size': 48,
            'retention_curve': _retention_curve(86, 73, 64, 56),
            'productivity_curve': _productivity_curve(start=4, end=13),
            'earnings_curve': _earnings_curve(weekly_inr=1_750),
            'drop_off_analysis': _drop_off([
                {'stage': 'signed_up', 'trainers_remaining': 48},
                {'stage': 'completed_kyc', 'trainers_remaining': 43},
                {'stage': 'first_task', 'trainers_remaining': 40},
                {'stage': 'first_payout', 'trainers_remaining': 36},
                {'stage': 'active_30_days', 'trainers_remaining': 32},
                {'stage': 'active_60_days', 'trainers_remaining': 28},
                {'stage': 'active_90_days', 'trainers_remaining': 24},
            ]),
        },
    ]


def _cohort_registration_week_mock() -> List[Dict[str, Any]]:
    """Same shape; rendered week-by-week instead of by wave label."""
    weeks = [
        {'cohort_id': '2026-W10', 'cohort_name': 'Week 10', 'cohort_start': '2026-03-02',
         'cohort_size': 18, 'retention': (84, 70, 58, 51), 'prod_start': 3, 'prod_end': 12, 'weekly': 1500},
        {'cohort_id': '2026-W14', 'cohort_name': 'Week 14', 'cohort_start': '2026-03-30',
         'cohort_size': 22, 'retention': (88, 75, 63, 55), 'prod_start': 4, 'prod_end': 14, 'weekly': 1800},
        {'cohort_id': '2026-W17', 'cohort_name': 'Week 17', 'cohort_start': '2026-04-20',
         'cohort_size': 31, 'retention': (91, 78, 66, 57), 'prod_start': 5, 'prod_end': 15, 'weekly': 1950},
        {'cohort_id': '2026-W20', 'cohort_name': 'Week 20', 'cohort_start': '2026-05-11',
         'cohort_size': 28, 'retention': (86, 72, 61, 54), 'prod_start': 4, 'prod_end': 13, 'weekly': 1750},
    ]
    out: List[Dict[str, Any]] = []
    for w in weeks:
        out.append({
            'cohort_id': w['cohort_id'],
            'cohort_name': w['cohort_name'],
            'cohort_start': w['cohort_start'],
            'cohort_size': w['cohort_size'],
            'retention_curve': _retention_curve(*w['retention']),
            'productivity_curve': _productivity_curve(w['prod_start'], w['prod_end']),
            'earnings_curve': _earnings_curve(w['weekly']),
            'drop_off_analysis': _drop_off([
                {'stage': 'signed_up', 'trainers_remaining': w['cohort_size']},
                {'stage': 'completed_kyc',
                 'trainers_remaining': int(w['cohort_size'] * 0.9)},
                {'stage': 'first_task',
                 'trainers_remaining': int(w['cohort_size'] * 0.84)},
                {'stage': 'first_payout',
                 'trainers_remaining': int(w['cohort_size'] * 0.76)},
                {'stage': 'active_30_days',
                 'trainers_remaining': int(w['cohort_size'] * 0.7 * w['retention'][1] / 100)},
                {'stage': 'active_60_days',
                 'trainers_remaining': int(w['cohort_size'] * 0.7 * w['retention'][2] / 100)},
                {'stage': 'active_90_days',
                 'trainers_remaining': int(w['cohort_size'] * 0.7 * w['retention'][3] / 100)},
            ]),
        })
    return out


def _cohort_tier_promotion_mock() -> List[Dict[str, Any]]:
    """Trainers grouped by the month they got promoted to silver/gold."""
    return [
        {
            'cohort_id': 'tier-mar-2026',
            'cohort_name': 'Promoted Mar 2026',
            'cohort_start': '2026-03-01',
            'cohort_size': 22,
            'retention_curve': _retention_curve(94, 88, 80, 74),
            'productivity_curve': _productivity_curve(8, 18),
            'earnings_curve': _earnings_curve(2_400),
            'drop_off_analysis': _drop_off([
                {'stage': 'promoted', 'trainers_remaining': 22},
                {'stage': 'first_tier_task', 'trainers_remaining': 22},
                {'stage': 'first_tier_payout', 'trainers_remaining': 21},
                {'stage': 'active_30_days', 'trainers_remaining': 20},
                {'stage': 'active_60_days', 'trainers_remaining': 18},
                {'stage': 'active_90_days', 'trainers_remaining': 16},
            ]),
        },
        {
            'cohort_id': 'tier-apr-2026',
            'cohort_name': 'Promoted Apr 2026',
            'cohort_start': '2026-04-01',
            'cohort_size': 28,
            'retention_curve': _retention_curve(93, 86, 78, 71),
            'productivity_curve': _productivity_curve(7, 17),
            'earnings_curve': _earnings_curve(2_250),
            'drop_off_analysis': _drop_off([
                {'stage': 'promoted', 'trainers_remaining': 28},
                {'stage': 'first_tier_task', 'trainers_remaining': 27},
                {'stage': 'first_tier_payout', 'trainers_remaining': 26},
                {'stage': 'active_30_days', 'trainers_remaining': 24},
                {'stage': 'active_60_days', 'trainers_remaining': 22},
                {'stage': 'active_90_days', 'trainers_remaining': 20},
            ]),
        },
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_cohort_metrics(
    cohort_definition: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the cohort metrics payload.

    Returns
    -------
    Dict with keys:
        * ``cohort_definition`` - normalised definition actually used
        * ``cohorts``           - list of cohort dicts (see module docstring)

    Each cohort dict has: cohort_id, cohort_name, cohort_start, cohort_size,
    retention_curve (4 points: day 7/30/60/90), productivity_curve (12 weeks),
    earnings_curve (12 weeks cumulative), drop_off_analysis.

    TODO Phase 2: replace with a real query joining Trainer.signup_at /
    Trainer.tier_promoted_at against the activity tables.
    """
    raw = (cohort_definition or _DEFAULT_COHORT_DEFINITION).strip().lower()
    cohort_definition_normalised = (
        raw if raw in _VALID_COHORT_DEFINITIONS else _DEFAULT_COHORT_DEFINITION
    )

    if cohort_definition_normalised == 'registration_week':
        cohorts = _cohort_registration_week_mock()
    elif cohort_definition_normalised == 'tier_promotion_month':
        cohorts = _cohort_tier_promotion_mock()
    else:
        cohorts = _cohort_signup_wave_mock()

    return {
        'cohort_definition': cohort_definition_normalised,
        'cohorts': cohorts,
    }
