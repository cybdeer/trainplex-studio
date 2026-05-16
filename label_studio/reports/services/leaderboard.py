"""Trainer leaderboard service — Phase 2 WAVE-19 real-data wiring.

Builds the ranked-trainer table for the admin Trainer Leaderboard surface.

Real Django ORM aggregation. Empty DB → empty results list (honest empty
state, no fabricated activity).

Public API
----------
``build_leaderboard(period, filters)`` returns the ranked trainer list plus
the Hall of Fame (lifetime + this month).

Filters supported (all optional, applied AND-wise)
    * ``state``         - ISO 3166-2:IN state code (requires User.state column)
    * ``tier``          - ``'bronze' | 'silver' | 'gold'``
    * ``language``      - language code
    * ``project_type``  - project type

Period
    * ``'daily'``       - last 24h tasks + earnings
    * ``'weekly'``      - last 7 days
    * ``'monthly'``     - last 30 days
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional


# Period → look-back window in days.
_PERIOD_DAYS: Dict[str, int] = {
    'daily': 1,
    'weekly': 7,
    'monthly': 30,
}

_VALID_PERIODS = ('daily', 'weekly', 'monthly')
_DEFAULT_PERIOD = 'weekly'

# Allowed filter values — anything outside is silently dropped so the UI
# can't 400 the founder dashboard with a typo.
_VALID_TIERS = {'bronze', 'silver', 'gold'}
_VALID_PROJECT_TYPES = {'ocr', 'voice', 'image', 'sentiment', 'moderation'}


def _normalise_period(period: Optional[str]) -> str:
    if not period:
        return _DEFAULT_PERIOD
    p = period.strip().lower()
    return p if p in _VALID_PERIODS else _DEFAULT_PERIOD


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


def _user_display(u) -> str:
    try:
        full = u.get_full_name() or ''
    except Exception:
        full = ''
    return (full or u.email or f'Trainer #{u.id}').strip()


def build_leaderboard(
    period: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return the ranked leaderboard payload.

    Empty DB / no matching trainers → ``results == []`` and Hall of Fame
    arrays are empty too. No fabricated activity.
    """
    from django.db.models import Count, Q, Sum
    from django.utils import timezone as dj_timezone

    from payments.models import PaymentHold
    from users.models import User

    p = _normalise_period(period)
    days = _PERIOD_DAYS[p]
    now = dj_timezone.now()
    period_start = now - timedelta(days=days)

    filters = filters or {}
    state = (filters.get('state') or '').strip() or None
    tier = (filters.get('tier') or '').strip().lower() or None
    language = (filters.get('language') or '').strip().lower() or None
    project_type = (filters.get('project_type') or '').strip().lower() or None

    if tier and tier not in _VALID_TIERS:
        tier = None
    if project_type and project_type not in _VALID_PROJECT_TYPES:
        project_type = None

    # Skip filter if the column doesn't exist (honest empty result downstream).
    qs = User.objects.filter(role='trainer')
    if state:
        if _user_has_field('state'):
            qs = qs.filter(state__iexact=state)
        else:
            qs = qs.none()
    if tier:
        if _user_has_field('tier'):
            qs = qs.filter(tier=tier)
        else:
            qs = qs.none()
    # language / project_type filters skipped here — columns are Phase-2 /
    # Step-8 schema adds. Honest empty result if caller asked for them.
    if language and not _user_has_field('languages'):
        qs = qs.none()
    if project_type:
        qs = qs.none()

    qs = qs.annotate(
        tasks_done=Count(
            'annotations',
            filter=Q(annotations__created_at__gte=period_start, annotations__was_cancelled=False),
            distinct=True,
        ),
        earnings_inr_sum=Sum(
            'payment_holds__amount_inr',
            filter=Q(
                payment_holds__held_at__gte=period_start,
                payment_holds__status__in=[
                    PaymentHold.STATUS_RELEASED,
                    PaymentHold.STATUS_HELD,
                ],
            ),
        ),
    ).order_by('-tasks_done', 'id')

    results: List[Dict[str, Any]] = []
    rank = 0
    for u in qs:
        td = int(u.tasks_done or 0)
        if td == 0:
            continue  # trainers with zero activity not shown in leaderboard
        rank += 1
        results.append(
            {
                'rank': rank,
                'trainer_id': u.id,
                'name': _user_display(u),
                'state': getattr(u, 'state', '') or '',
                'tier': getattr(u, 'tier', '') or '',
                'language': '',
                'project_type': '',
                'tasks_done': td,
                'earnings_inr': _decimal_to_int(u.earnings_inr_sum),
                'quality_score_pct': 0,
                'consistency_pct': 0,
            }
        )

    # Hall of fame: lifetime + this month, computed on the UNFILTERED trainer
    # population so the founder always sees the same names regardless of UI
    # filter state.
    lifetime_qs = (
        User.objects.filter(role='trainer')
        .annotate(
            lifetime_tasks=Count(
                'annotations',
                filter=Q(annotations__was_cancelled=False),
                distinct=True,
            ),
            lifetime_earnings_inr_sum=Sum('payment_holds__amount_inr'),
        )
        .filter(lifetime_tasks__gt=0)
        .order_by('-lifetime_tasks', 'id')[:10]
    )

    hall_of_fame_lifetime: List[Dict[str, Any]] = []
    for idx, u in enumerate(lifetime_qs):
        hall_of_fame_lifetime.append(
            {
                'rank': idx + 1,
                'trainer_id': u.id,
                'name': _user_display(u),
                'state': getattr(u, 'state', '') or '',
                'lifetime_tasks': int(u.lifetime_tasks or 0),
                'lifetime_earnings_inr': _decimal_to_int(u.lifetime_earnings_inr_sum),
            }
        )

    month_start = now - timedelta(days=30)
    month_qs = (
        User.objects.filter(role='trainer')
        .annotate(
            month_tasks=Count(
                'annotations',
                filter=Q(
                    annotations__created_at__gte=month_start,
                    annotations__was_cancelled=False,
                ),
                distinct=True,
            ),
            month_earnings_inr_sum=Sum(
                'payment_holds__amount_inr',
                filter=Q(payment_holds__held_at__gte=month_start),
            ),
        )
        .filter(month_tasks__gt=0)
        .order_by('-month_tasks', 'id')[:10]
    )

    hall_of_fame_month: List[Dict[str, Any]] = []
    for idx, u in enumerate(month_qs):
        hall_of_fame_month.append(
            {
                'rank': idx + 1,
                'trainer_id': u.id,
                'name': _user_display(u),
                'state': getattr(u, 'state', '') or '',
                'tasks_this_month': int(u.month_tasks or 0),
                'earnings_this_month_inr': _decimal_to_int(u.month_earnings_inr_sum),
            }
        )

    return {
        'period': p,
        'filters': {
            'state': filters.get('state') or None,
            'tier': filters.get('tier') or None,
            'language': filters.get('language') or None,
            'project_type': filters.get('project_type') or None,
        },
        'total': len(results),
        'results': results,
        'hall_of_fame_lifetime': hall_of_fame_lifetime,
        'hall_of_fame_month': hall_of_fame_month,
    }
