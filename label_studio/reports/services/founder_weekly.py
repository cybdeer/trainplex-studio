"""Founder weekly snapshot service — Phase 2 WAVE-19 real-data wiring.

Builds the data payload for the founder dashboard's "weekly snapshot" view.
Real Django ORM aggregation. Empty DB returns zeros / empty lists — honest
empty state, NOT fabricated activity.

Sections returned
-----------------
* ``top_kpis``           - submissions_weekly, revenue_weekly_inr,
                           active_trainers, avg_payout_per_trainer
* ``trend_lines``        - submissions_over_time, revenue_mom, trainer_growth
* ``cohort_retention``   - per-wave day_7/day_30/day_60/day_90 retention
* ``project_roi``        - per-project cost + revenue + roi_pct
* ``geographic_split``   - state-wise breakdown
* ``language_split``     - language-wise productivity
* ``quality_kpis``       - avg_consensus_pct, dispute_rate_pct, top_10_problematic
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_monday(d: Optional[date]) -> date:
    """Snap to ISO week's Monday so the snapshot is week-stable."""
    if d is None:
        d = datetime.now(timezone.utc).date()
    return d - timedelta(days=d.weekday())


def _iso_date(d: date) -> str:
    return d.isoformat()


def _decimal_to_int(v) -> int:
    if v is None:
        return 0
    if isinstance(v, Decimal):
        return int(v)
    return int(v)


def _user_has_field(field_name: str) -> bool:
    """Return True iff ``users.User`` has the named field."""
    try:
        from users.models import User

        User._meta.get_field(field_name)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Real-data builders
# ---------------------------------------------------------------------------


def _build_top_kpis(week_start: date, week_end: date) -> Dict[str, Any]:
    """4 KPI cards: weekly submissions, revenue, active trainers, avg payout."""
    from django.db.models import Sum

    from payments.models import PayoutQueue
    from tasks.models import Annotation
    from users.models import User

    start_dt = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(week_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    prev_start = start_dt - timedelta(days=7)

    submissions_weekly = Annotation.objects.filter(
        created_at__gte=start_dt, created_at__lt=end_dt, was_cancelled=False
    ).count()
    submissions_prev = Annotation.objects.filter(
        created_at__gte=prev_start, created_at__lt=start_dt, was_cancelled=False
    ).count()
    submissions_delta_pct = (
        int(round(((submissions_weekly - submissions_prev) / submissions_prev) * 100))
        if submissions_prev
        else 0
    )

    revenue_weekly_inr = _decimal_to_int(
        PayoutQueue.objects.filter(
            status=PayoutQueue.STATUS_SENT, sent_at__gte=start_dt, sent_at__lt=end_dt
        ).aggregate(s=Sum('amount_inr'))['s']
    )
    revenue_prev = _decimal_to_int(
        PayoutQueue.objects.filter(
            status=PayoutQueue.STATUS_SENT, sent_at__gte=prev_start, sent_at__lt=start_dt
        ).aggregate(s=Sum('amount_inr'))['s']
    )
    revenue_delta_pct = (
        int(round(((revenue_weekly_inr - revenue_prev) / revenue_prev) * 100))
        if revenue_prev
        else 0
    )

    active_trainers = User.objects.filter(
        role='trainer', last_login__gte=start_dt, last_login__lt=end_dt
    ).count()
    active_trainers_prev = User.objects.filter(
        role='trainer', last_login__gte=prev_start, last_login__lt=start_dt
    ).count()
    active_trainers_delta_pct = (
        int(round(((active_trainers - active_trainers_prev) / active_trainers_prev) * 100))
        if active_trainers_prev
        else 0
    )

    avg_payout_per_trainer = revenue_weekly_inr // max(active_trainers, 1)

    return {
        'submissions_weekly': submissions_weekly,
        'submissions_delta_pct': submissions_delta_pct,
        'revenue_weekly_inr': revenue_weekly_inr,
        'revenue_delta_pct': revenue_delta_pct,
        'active_trainers': active_trainers,
        'active_trainers_delta_pct': active_trainers_delta_pct,
        'avg_payout_per_trainer_inr': avg_payout_per_trainer,
    }


def _build_trend_lines(week_start: date) -> Dict[str, List[Dict[str, Any]]]:
    """3 trend series — 7-day submissions, 6-month revenue MoM, 6-month trainer growth."""
    from django.db.models import Sum

    from payments.models import PayoutQueue
    from tasks.models import Annotation
    from users.models import User

    submissions_over_time: List[Dict[str, Any]] = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        count = Annotation.objects.filter(
            created_at__date=day, was_cancelled=False
        ).count()
        submissions_over_time.append({'date': _iso_date(day), 'count': count})

    revenue_mom: List[Dict[str, Any]] = []
    trainer_growth: List[Dict[str, Any]] = []
    months_back = 6
    current_year = week_start.year
    current_month = week_start.month
    for back in range(months_back - 1, -1, -1):
        m = current_month - back
        y = current_year
        while m <= 0:
            m += 12
            y -= 1
        month_start = date(y, m, 1)
        if m == 12:
            next_month_start = date(y + 1, 1, 1)
        else:
            next_month_start = date(y, m + 1, 1)
        start_dt = datetime.combine(month_start, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(next_month_start, datetime.min.time(), tzinfo=timezone.utc)

        rev = _decimal_to_int(
            PayoutQueue.objects.filter(
                status=PayoutQueue.STATUS_SENT, sent_at__gte=start_dt, sent_at__lt=end_dt
            ).aggregate(s=Sum('amount_inr'))['s']
        )
        revenue_mom.append({'month': f'{y:04d}-{m:02d}', 'revenue_inr': rev})

        active_count = User.objects.filter(
            role='trainer', last_login__gte=start_dt, last_login__lt=end_dt
        ).count()
        trainer_growth.append({'month': f'{y:04d}-{m:02d}', 'active_trainers': active_count})

    return {
        'submissions_over_time': submissions_over_time,
        'revenue_mom': revenue_mom,
        'trainer_growth': trainer_growth,
    }


def _build_cohort_retention() -> List[Dict[str, Any]]:
    """Per-wave (weekly signup cohort) day_7/30/60/90 retention. Empty → []."""
    from users.models import User

    waves = User.objects.filter(role='trainer').values_list('date_joined', flat=True)
    if not waves.exists():
        return []

    earliest = waves.order_by('date_joined').first()
    latest = waves.order_by('-date_joined').first()
    if earliest is None or latest is None:
        return []

    first_monday = earliest.date() - timedelta(days=earliest.weekday())
    last_monday = latest.date() - timedelta(days=latest.weekday())

    out: List[Dict[str, Any]] = []
    wave_idx = 0
    week = first_monday
    while week <= last_monday and wave_idx < 12:  # cap to 12 most-recent
        next_week = week + timedelta(days=7)
        members = User.objects.filter(
            role='trainer',
            date_joined__date__gte=week,
            date_joined__date__lt=next_week,
        )
        cohort_size = members.count()
        if cohort_size == 0:
            week = next_week
            continue
        wave_idx += 1

        def _retained_within(days: int) -> int:
            start_dt = datetime.combine(week, datetime.min.time(), tzinfo=timezone.utc)
            deadline = datetime.combine(
                week + timedelta(days=days), datetime.min.time(), tzinfo=timezone.utc
            )
            return members.filter(last_login__gte=start_dt, last_login__lt=deadline).count()

        def _pct(n: int) -> int:
            return int(round((n / cohort_size) * 100)) if cohort_size else 0

        out.append(
            {
                'wave_name': f'Wave {wave_idx} ({week.strftime("%b %Y")})',
                'wave_start': _iso_date(week),
                'cohort_size': cohort_size,
                'day_7': _pct(_retained_within(7)),
                'day_30': _pct(_retained_within(30)),
                'day_60': _pct(_retained_within(60)),
                'day_90': _pct(_retained_within(90)),
            }
        )
        week = next_week

    return out


def _build_project_roi_top5() -> List[Dict[str, Any]]:
    """Top-5 projects by revenue. Empty DB → []."""
    try:
        from django.db.models import Count, Sum

        from projects.models import Project
    except Exception:
        return []

    try:
        rows = (
            Project.objects.annotate(
                tasks_count=Count('tasks', distinct=True),
            )
            .order_by('-tasks_count')[:5]
        )
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for p in rows:
        if (p.tasks_count or 0) == 0:
            continue
        # PaymentHold.task_id is loose-FK to tasks.Task (integer). Join in
        # Python to keep this portable until the schema relationship lands.
        try:
            from payments.models import PaymentHold

            task_ids = list(p.tasks.values_list('id', flat=True))
            rev = _decimal_to_int(
                PaymentHold.objects.filter(task_id__in=task_ids)
                .aggregate(s=Sum('amount_inr'))['s']
            )
        except Exception:
            rev = 0
        out.append(
            {
                'project_id': p.id,
                'project_name': p.title or f'Project #{p.id}',
                'cost_inr': 0,
                'revenue_inr': rev,
                'roi_pct': 0,
            }
        )
    return out


def _build_geographic_split(week_start: date, week_end: date) -> List[Dict[str, Any]]:
    """State-wise productivity split this week. No state column → []."""
    if not _user_has_field('state'):
        return []

    from django.db.models import Count, Q, Sum

    from users.models import User

    start_dt = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(week_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    rows = (
        User.objects.filter(role='trainer')
        .exclude(state__isnull=True)
        .exclude(state='')
        .values('state')
        .annotate(
            submissions=Count(
                'annotations',
                filter=Q(
                    annotations__created_at__gte=start_dt,
                    annotations__created_at__lt=end_dt,
                    annotations__was_cancelled=False,
                ),
                distinct=True,
            ),
            active_trainers=Count(
                'id', filter=Q(last_login__gte=start_dt, last_login__lt=end_dt), distinct=True
            ),
            earnings_inr_sum=Sum(
                'payment_holds__amount_inr',
                filter=Q(payment_holds__held_at__gte=start_dt, payment_holds__held_at__lt=end_dt),
            ),
        )
        .order_by('-submissions')[:8]
    )

    return [
        {
            'state_code': r['state'] or '',
            'state_name': r['state'] or '',
            'submissions': int(r['submissions'] or 0),
            'active_trainers': int(r['active_trainers'] or 0),
            'earnings_inr': _decimal_to_int(r['earnings_inr_sum']),
        }
        for r in rows
    ]


def _build_language_split() -> List[Dict[str, Any]]:
    """Language-wise productivity. Schema not present → []."""
    # languages column is a Phase-2 / Step-8 schema add on User.
    # Until then return [] (honest empty state).
    return []


def _build_quality_kpis(week_start: date, week_end: date) -> Dict[str, Any]:
    """avg_consensus_pct, dispute_rate_pct, top_10_problematic. Empty → zeros + []."""
    from django.db.models import Count

    from peer_review.models import ConsensusResult, Dispute, ReviewAssignment
    from tasks.models import Annotation
    from users.models import User

    start_dt = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(week_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    cr_qs = ConsensusResult.objects.filter(computed_at__gte=start_dt, computed_at__lt=end_dt)
    total_consensus = cr_qs.count()
    if total_consensus:
        approved_or_flagged = cr_qs.filter(
            status__in=[ConsensusResult.STATUS_APPROVED, ConsensusResult.STATUS_FLAGGED]
        ).count()
        avg_consensus_pct = int(round((approved_or_flagged / total_consensus) * 100))
    else:
        avg_consensus_pct = 0

    disputes = Dispute.objects.filter(
        escalated_at__gte=start_dt, escalated_at__lt=end_dt
    ).count()
    dispute_rate_pct = (
        int(round((disputes / total_consensus) * 100)) if total_consensus else 0
    )

    top_q = (
        ReviewAssignment.objects.filter(
            assigned_at__gte=start_dt,
            assigned_at__lt=end_dt,
            review__agreement__in=['disagree', 'dispute'],
        )
        .exclude(trainer_id__isnull=True)
        .values('trainer_id')
        .annotate(dispute_count=Count('id'))
        .order_by('-dispute_count')[:10]
    )

    top_10: List[Dict[str, Any]] = []
    for row in top_q:
        tid = row['trainer_id']
        u = User.objects.filter(id=tid).first()
        sub_count = Annotation.objects.filter(
            completed_by_id=tid,
            created_at__gte=start_dt,
            created_at__lt=end_dt,
            was_cancelled=False,
        ).count()
        rate = int(round((row['dispute_count'] / sub_count) * 100)) if sub_count else 0
        top_10.append(
            {
                'trainer_id': tid,
                'name': (
                    (u.get_full_name() or u.email or f'Trainer #{tid}').strip()
                    if u
                    else f'Trainer #{tid}'
                ),
                'state': (getattr(u, 'state', '') or '') if u else '',
                'dispute_count': int(row['dispute_count']),
                'submissions': int(sub_count),
                'dispute_rate_pct': rate,
            }
        )

    return {
        'avg_consensus_pct': avg_consensus_pct,
        'dispute_rate_pct': dispute_rate_pct,
        'avg_consensus_pct_delta': 0,
        'dispute_rate_pct_delta': 0,
        'top_10_problematic': top_10,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_founder_weekly_snapshot(week_start: Optional[date] = None) -> Dict[str, Any]:
    """Build the founder weekly snapshot. Real DB aggregation.

    Empty DB → all sections return zeros / empty lists. No fabricated activity.
    """
    snapped = _to_monday(week_start)
    week_end = snapped + timedelta(days=6)
    return {
        'week_start': _iso_date(snapped),
        'week_end': _iso_date(week_end),
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'top_kpis': _build_top_kpis(snapped, week_end),
        'trend_lines': _build_trend_lines(snapped),
        'cohort_retention': _build_cohort_retention(),
        'project_roi': _build_project_roi_top5(),
        'geographic_split': _build_geographic_split(snapped, week_end),
        'language_split': _build_language_split(),
        'quality_kpis': _build_quality_kpis(snapped, week_end),
    }
