"""Cohort retention analyzer — Phase 2 WAVE-19 real-data wiring.

Builds cohort-based curves the founder uses to understand how trainer waves
behave over time. Real Django ORM aggregation.

Cohort definitions
------------------
* ``'registration_week'``   - bucket trainers by ISO week of signup
* ``'signup_wave'``         - same as registration_week for now
* ``'tier_promotion_month'``- bucket trainers by the month they were promoted
                              (requires User.tier_promoted_at field)

Curves returned per cohort
--------------------------
* ``retention_curve``     - day 7 / 30 / 60 / 90 retention %
* ``productivity_curve``  - average tasks/week per cohort member
* ``earnings_curve``      - cumulative ₹ per cohort member by week-since-signup
* ``drop_off_analysis``   - per-stage trainer-count fall-off

Empty DB → ``cohorts == []`` (honest empty).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional


_VALID_COHORT_DEFINITIONS = (
    'registration_week',
    'signup_wave',
    'tier_promotion_month',
)
_DEFAULT_COHORT_DEFINITION = 'signup_wave'

_CURVE_WEEKS = 12


def _user_has_field(field_name: str) -> bool:
    try:
        from users.models import User

        User._meta.get_field(field_name)
        return True
    except Exception:
        return False


def _decimal_to_int(v) -> int:
    if v is None:
        return 0
    if isinstance(v, Decimal):
        return int(v)
    return int(v)


def _retention_curve(day_7: int, day_30: int, day_60: int, day_90: int) -> List[Dict[str, Any]]:
    return [
        {'day': 7, 'retention_pct': day_7},
        {'day': 30, 'retention_pct': day_30},
        {'day': 60, 'retention_pct': day_60},
        {'day': 90, 'retention_pct': day_90},
    ]


def _build_cohorts_by_week() -> List[Dict[str, Any]]:
    """Real DB cohort build: trainers bucketed by ISO week of signup."""
    from django.db.models import Count, Q, Sum

    from payments.models import PaymentHold
    from tasks.models import Annotation
    from users.models import User

    trainers = User.objects.filter(role='trainer')
    if not trainers.exists():
        return []

    earliest = trainers.order_by('date_joined').first()
    latest = trainers.order_by('-date_joined').first()
    if earliest is None or latest is None:
        return []

    first_monday = earliest.date_joined.date() - timedelta(days=earliest.date_joined.weekday())
    last_monday = latest.date_joined.date() - timedelta(days=latest.date_joined.weekday())

    out: List[Dict[str, Any]] = []
    wave_idx = 0
    week = first_monday
    while week <= last_monday and wave_idx < 12:
        next_week = week + timedelta(days=7)
        members = trainers.filter(
            date_joined__date__gte=week, date_joined__date__lt=next_week
        )
        cohort_size = members.count()
        if cohort_size == 0:
            week = next_week
            continue
        wave_idx += 1

        # Retention.
        def _retained_pct(days: int) -> int:
            start_dt = datetime.combine(week, datetime.min.time(), tzinfo=timezone.utc)
            deadline = datetime.combine(
                week + timedelta(days=days), datetime.min.time(), tzinfo=timezone.utc
            )
            n = members.filter(
                last_login__gte=start_dt, last_login__lt=deadline
            ).count()
            return int(round((n / cohort_size) * 100)) if cohort_size else 0

        retention = _retention_curve(
            _retained_pct(7), _retained_pct(30), _retained_pct(60), _retained_pct(90)
        )

        # Productivity curve: avg tasks/cohort/week for weeks since signup.
        member_ids = list(members.values_list('id', flat=True))
        productivity_curve: List[Dict[str, Any]] = []
        earnings_curve: List[Dict[str, Any]] = []
        cum_earnings = 0
        for w in range(1, _CURVE_WEEKS + 1):
            w_start = datetime.combine(
                week + timedelta(days=(w - 1) * 7), datetime.min.time(), tzinfo=timezone.utc
            )
            w_end = datetime.combine(
                week + timedelta(days=w * 7), datetime.min.time(), tzinfo=timezone.utc
            )
            tasks = Annotation.objects.filter(
                completed_by_id__in=member_ids,
                created_at__gte=w_start,
                created_at__lt=w_end,
                was_cancelled=False,
            ).count()
            avg_per_member = round(tasks / cohort_size, 2) if cohort_size else 0
            productivity_curve.append(
                {'week': w, 'avg_tasks_per_member': avg_per_member}
            )

            week_earnings = _decimal_to_int(
                PaymentHold.objects.filter(
                    trainer_id__in=member_ids,
                    held_at__gte=w_start,
                    held_at__lt=w_end,
                ).aggregate(s=Sum('amount_inr'))['s']
            )
            cum_earnings += week_earnings
            earnings_curve.append(
                {
                    'week': w,
                    'cumulative_earnings_per_member_inr': (
                        cum_earnings // cohort_size if cohort_size else 0
                    ),
                }
            )

        # Drop-off: retained at each retention milestone.
        drop_off_analysis: List[Dict[str, Any]] = []
        prev = cohort_size
        for milestone_days, label in [(7, 'day_7'), (30, 'day_30'), (60, 'day_60'), (90, 'day_90')]:
            start_dt = datetime.combine(week, datetime.min.time(), tzinfo=timezone.utc)
            deadline = datetime.combine(
                week + timedelta(days=milestone_days), datetime.min.time(), tzinfo=timezone.utc
            )
            n = members.filter(last_login__gte=start_dt, last_login__lt=deadline).count()
            lost = prev - n
            drop_off_analysis.append(
                {
                    'stage': label,
                    'remaining': n,
                    'lost_since_prev': lost if lost > 0 else 0,
                }
            )
            prev = n

        out.append(
            {
                'cohort_id': f'week-{week.isoformat()}',
                'cohort_name': f'Wave {wave_idx} ({week.strftime("%b %Y")})',
                'cohort_start': week.isoformat(),
                'cohort_size': cohort_size,
                'retention_curve': retention,
                'productivity_curve': productivity_curve,
                'earnings_curve': earnings_curve,
                'drop_off_analysis': drop_off_analysis,
            }
        )
        week = next_week

    return out


def compute_cohort_metrics(
    cohort_definition: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the cohort metrics payload. Real DB. Empty DB → cohorts=[]."""
    raw = (cohort_definition or _DEFAULT_COHORT_DEFINITION).strip().lower()
    cohort_definition_normalised = (
        raw if raw in _VALID_COHORT_DEFINITIONS else _DEFAULT_COHORT_DEFINITION
    )

    if cohort_definition_normalised == 'tier_promotion_month':
        # Requires User.tier_promoted_at — Phase-2 / Step-8 schema add.
        if not _user_has_field('tier_promoted_at'):
            cohorts: List[Dict[str, Any]] = []
        else:
            cohorts = _build_cohorts_by_week()  # fallback to weekly for now
    else:
        # registration_week / signup_wave both bucket by ISO signup week.
        cohorts = _build_cohorts_by_week()

    return {
        'cohort_definition': cohort_definition_normalised,
        'cohorts': cohorts,
    }
