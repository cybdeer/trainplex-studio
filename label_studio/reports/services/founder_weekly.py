"""Founder weekly snapshot service — Phase 1 Step 7.

Builds the data payload for the founder dashboard's "weekly snapshot" view.
Includes all sections the UI renders:

* ``top_kpis``           - submissions_weekly, revenue_weekly_inr,
                           active_trainers, avg_payout_per_trainer
* ``trend_lines``        - submissions_over_time, revenue_mom, trainer_growth
* ``cohort_retention``   - per-wave day_7/day_30/day_60/day_90 retention
* ``project_roi``        - per-project cost + revenue + roi_pct
* ``geographic_split``   - state-wise breakdown (reuses heatmap shape)
* ``language_split``     - language-wise productivity
* ``quality_kpis``       - avg_consensus_pct, dispute_rate_pct, top_10_problematic

Phase 1 (Week 7): all numbers are MOCK. The shape is pinned by
``test_reports.py`` so the React surface stays stable when the real
aggregation lands in Phase 2 / Step 8.

TODO Phase 2: replace ``build_founder_weekly_snapshot`` with a single
``WeeklySnapshot.compute(week_start)`` that joins SUBMISSIONS + PAYMENTS +
TRAINERS + PROJECTS, then memoises into a ``WeeklySnapshotCache`` row keyed
on ``week_start`` so the founder dashboard hits Postgres once per week.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_monday(d: Optional[date]) -> date:
    """Snap to ISO week's Monday so the snapshot is week-stable.

    If no date is supplied, defaults to the Monday of the current ISO week.
    Snapping ensures ``build_founder_weekly_snapshot(week_start=any-weekday)``
    always returns the same payload for that week — the auto-email cron and
    the manual founder fetch can never disagree.
    """
    if d is None:
        d = datetime.now(timezone.utc).date()
    return d - timedelta(days=d.weekday())


def _iso_date(d: date) -> str:
    return d.isoformat()


# ---------------------------------------------------------------------------
# Mock data builders — DETERMINISTIC, period-stable
# ---------------------------------------------------------------------------


def _mock_top_kpis() -> Dict[str, Any]:
    """4 KPI cards across the top of the founder dashboard.

    avg_payout_per_trainer is a derived value (revenue_weekly / active_trainers
    rounded to whole rupees) so the UI doesn't have to compute it.
    """
    submissions_weekly = 8420
    revenue_weekly_inr = 412_500
    active_trainers = 138
    # Whole rupees; rounded so the UI shows "₹2,989" not "2989.13".
    avg_payout_per_trainer = revenue_weekly_inr // max(active_trainers, 1)
    return {
        'submissions_weekly': submissions_weekly,
        'submissions_delta_pct': 8,
        'revenue_weekly_inr': revenue_weekly_inr,
        'revenue_delta_pct': 12,
        'active_trainers': active_trainers,
        'active_trainers_delta_pct': 4,
        'avg_payout_per_trainer_inr': avg_payout_per_trainer,
    }


def _mock_trend_lines(week_start: date) -> Dict[str, List[Dict[str, Any]]]:
    """3 trend series — 7-day submissions, 6-month revenue MoM, 6-month trainer growth.

    The week_start is reflected in the date axis so the chart x-labels stay
    correct across weeks. Numbers themselves are deterministic via a simple
    series; the magnitude matches the top KPI for sanity.
    """
    submissions_over_time: List[Dict[str, Any]] = []
    # 7 days, monotone-ish, totalling ~ submissions_weekly.
    base = 1100
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        # Modest day-of-week variation (lower on Sat/Sun).
        weekday_factor = 0.7 if day.weekday() >= 5 else 1.0
        count = int(base * weekday_factor + (offset * 25))
        submissions_over_time.append(
            {'date': _iso_date(day), 'count': count}
        )

    revenue_mom: List[Dict[str, Any]] = []
    months_back = 6
    # Anchor at month-of(week_start) and step backwards.
    current_year = week_start.year
    current_month = week_start.month
    for back in range(months_back - 1, -1, -1):
        m = current_month - back
        y = current_year
        while m <= 0:
            m += 12
            y -= 1
        # Smooth growth curve from 280k → 412k.
        rev = 280_000 + (months_back - 1 - back) * 22_000
        revenue_mom.append(
            {'month': f'{y:04d}-{m:02d}', 'revenue_inr': rev}
        )

    trainer_growth: List[Dict[str, Any]] = []
    # Same x-axis as revenue_mom; trainer count from 78 → 138.
    for idx, entry in enumerate(revenue_mom):
        count = 78 + idx * 12
        trainer_growth.append(
            {'month': entry['month'], 'active_trainers': count}
        )

    return {
        'submissions_over_time': submissions_over_time,
        'revenue_mom': revenue_mom,
        'trainer_growth': trainer_growth,
    }


def _mock_cohort_retention() -> List[Dict[str, Any]]:
    """4 cohort waves with day_7/30/60/90 retention percentages.

    Real signup waves once the trainer-onboarding signal lands. For Phase 1
    these are anchored to the canonical "first 4 hiring drives" so the founder
    can pattern-recognise which wave converted best.
    """
    return [
        {
            'wave_name': 'Wave 1 (Mar 2026)',
            'wave_start': '2026-03-04',
            'cohort_size': 42,
            'day_7': 88,
            'day_30': 74,
            'day_60': 62,
            'day_90': 55,
        },
        {
            'wave_name': 'Wave 2 (Mar 2026)',
            'wave_start': '2026-03-25',
            'cohort_size': 38,
            'day_7': 84,
            'day_30': 71,
            'day_60': 60,
            'day_90': 52,
        },
        {
            'wave_name': 'Wave 3 (Apr 2026)',
            'wave_start': '2026-04-08',
            'cohort_size': 56,
            'day_7': 91,
            'day_30': 79,
            'day_60': 66,
            'day_90': 58,
        },
        {
            'wave_name': 'Wave 4 (Apr 2026)',
            'wave_start': '2026-04-29',
            'cohort_size': 48,
            'day_7': 86,
            'day_30': 73,
            'day_60': 64,
            'day_90': 56,
        },
    ]


def _mock_project_roi_per_project() -> List[Dict[str, Any]]:
    """Mini per-project ROI table that sits inside the founder dashboard.

    Full breakdown lives at /admin/reports/project-roi; this one is a
    top-5 summary for the founder snapshot.
    """
    return [
        {
            'project_id': 101,
            'project_name': 'KYC OCR — Hindi',
            'cost_inr': 145_000,
            'revenue_inr': 285_000,
            'roi_pct': 96,
        },
        {
            'project_id': 102,
            'project_name': 'Voice intent — Bhojpuri',
            'cost_inr': 92_000,
            'revenue_inr': 158_000,
            'roi_pct': 72,
        },
        {
            'project_id': 103,
            'project_name': 'Receipt extract — Tamil',
            'cost_inr': 68_000,
            'revenue_inr': 118_000,
            'roi_pct': 74,
        },
        {
            'project_id': 104,
            'project_name': 'Sentiment — Marathi',
            'cost_inr': 54_000,
            'revenue_inr': 84_000,
            'roi_pct': 56,
        },
        {
            'project_id': 105,
            'project_name': 'Image moderation',
            'cost_inr': 48_000,
            'revenue_inr': 62_000,
            'roi_pct': 29,
        },
    ]


def _mock_geographic_split() -> List[Dict[str, Any]]:
    """State-wise productivity split (mirrors heatmap shape).

    Top 8 states by submissions this week — full 17-state map lives at
    /admin/heatmap.
    """
    return [
        {'state_code': 'RJ', 'state_name': 'Rajasthan', 'submissions': 1320,
         'active_trainers': 22, 'earnings_inr': 68_000},
        {'state_code': 'UP', 'state_name': 'Uttar Pradesh', 'submissions': 1180,
         'active_trainers': 19, 'earnings_inr': 58_000},
        {'state_code': 'MH', 'state_name': 'Maharashtra', 'submissions': 980,
         'active_trainers': 16, 'earnings_inr': 52_000},
        {'state_code': 'KA', 'state_name': 'Karnataka', 'submissions': 920,
         'active_trainers': 15, 'earnings_inr': 48_500},
        {'state_code': 'GJ', 'state_name': 'Gujarat', 'submissions': 840,
         'active_trainers': 14, 'earnings_inr': 44_000},
        {'state_code': 'TN', 'state_name': 'Tamil Nadu', 'submissions': 720,
         'active_trainers': 12, 'earnings_inr': 38_500},
        {'state_code': 'MP', 'state_name': 'Madhya Pradesh', 'submissions': 640,
         'active_trainers': 11, 'earnings_inr': 32_000},
        {'state_code': 'PB', 'state_name': 'Punjab', 'submissions': 580,
         'active_trainers': 10, 'earnings_inr': 28_500},
    ]


def _mock_language_split() -> List[Dict[str, Any]]:
    """Language-wise productivity — submissions + avg_quality_pct.

    Useful for founder pattern-recognition: low-quality languages indicate
    where the training data needs more glossary work or the reviewer panel
    needs more bilingual coverage.
    """
    return [
        {'language_code': 'hi', 'language_name': 'Hindi',
         'submissions': 2480, 'avg_quality_pct': 89},
        {'language_code': 'bn', 'language_name': 'Bengali',
         'submissions': 1180, 'avg_quality_pct': 86},
        {'language_code': 'mr', 'language_name': 'Marathi',
         'submissions': 920, 'avg_quality_pct': 84},
        {'language_code': 'ta', 'language_name': 'Tamil',
         'submissions': 880, 'avg_quality_pct': 88},
        {'language_code': 'te', 'language_name': 'Telugu',
         'submissions': 760, 'avg_quality_pct': 85},
        {'language_code': 'gu', 'language_name': 'Gujarati',
         'submissions': 640, 'avg_quality_pct': 83},
        {'language_code': 'kn', 'language_name': 'Kannada',
         'submissions': 560, 'avg_quality_pct': 82},
        {'language_code': 'pa', 'language_name': 'Punjabi',
         'submissions': 480, 'avg_quality_pct': 87},
        {'language_code': 'bho', 'language_name': 'Bhojpuri',
         'submissions': 320, 'avg_quality_pct': 79},
        {'language_code': 'or', 'language_name': 'Odia',
         'submissions': 200, 'avg_quality_pct': 81},
    ]


def _mock_quality_kpis() -> Dict[str, Any]:
    """Quality KPIs: avg consensus, dispute rate, top-10 problematic trainers."""
    return {
        'avg_consensus_pct': 87,
        'dispute_rate_pct': 4,
        'avg_consensus_pct_delta': 2,
        'dispute_rate_pct_delta': -1,
        'top_10_problematic': [
            {'trainer_id': 42, 'name': 'Trainer #42', 'state': 'UP',
             'dispute_count': 8, 'submissions': 60, 'dispute_rate_pct': 13},
            {'trainer_id': 91, 'name': 'Trainer #91', 'state': 'Bihar',
             'dispute_count': 7, 'submissions': 55, 'dispute_rate_pct': 12},
            {'trainer_id': 17, 'name': 'Trainer #17', 'state': 'MP',
             'dispute_count': 6, 'submissions': 52, 'dispute_rate_pct': 11},
            {'trainer_id': 64, 'name': 'Trainer #64', 'state': 'RJ',
             'dispute_count': 6, 'submissions': 58, 'dispute_rate_pct': 10},
            {'trainer_id': 102, 'name': 'Trainer #102', 'state': 'MH',
             'dispute_count': 5, 'submissions': 50, 'dispute_rate_pct': 10},
            {'trainer_id': 33, 'name': 'Trainer #33', 'state': 'KA',
             'dispute_count': 5, 'submissions': 54, 'dispute_rate_pct': 9},
            {'trainer_id': 78, 'name': 'Trainer #78', 'state': 'GJ',
             'dispute_count': 4, 'submissions': 48, 'dispute_rate_pct': 8},
            {'trainer_id': 12, 'name': 'Trainer #12', 'state': 'TN',
             'dispute_count': 4, 'submissions': 52, 'dispute_rate_pct': 8},
            {'trainer_id': 55, 'name': 'Trainer #55', 'state': 'AP',
             'dispute_count': 3, 'submissions': 42, 'dispute_rate_pct': 7},
            {'trainer_id': 86, 'name': 'Trainer #86', 'state': 'WB',
             'dispute_count': 3, 'submissions': 46, 'dispute_rate_pct': 7},
        ],
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_founder_weekly_snapshot(week_start: Optional[date] = None) -> Dict[str, Any]:
    """Build the founder weekly snapshot.

    Parameters
    ----------
    week_start:
        Anchor for the week. Snapped to its ISO Monday so the snapshot is
        week-stable. Defaults to the Monday of the current ISO week.

    Returns
    -------
    Dict[str, Any]
        Stable JSON-serialisable contract. See module docstring for the keys.

    TODO Phase 2: real DB wiring. The current implementation is deterministic
    mock data so the React surface can be built + pinned by tests until the
    Phase 2 SUBMISSIONS / PAYMENTS / TRAINERS schema lands.
    """
    snapped = _to_monday(week_start)
    week_end = snapped + timedelta(days=6)
    return {
        'week_start': _iso_date(snapped),
        'week_end': _iso_date(week_end),
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'top_kpis': _mock_top_kpis(),
        'trend_lines': _mock_trend_lines(snapped),
        'cohort_retention': _mock_cohort_retention(),
        'project_roi': _mock_project_roi_per_project(),
        'geographic_split': _mock_geographic_split(),
        'language_split': _mock_language_split(),
        'quality_kpis': _mock_quality_kpis(),
    }
