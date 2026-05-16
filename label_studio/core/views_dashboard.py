"""TrainPlex Admin Dashboard widget — Phase 2 WAVE-19 real-data wiring.

Founder-facing one-screen ops snapshot. Login hote hi: aaj ke submissions,
kitne pay-hold, top 5 trainers state-wise, alerts ka counter.

Endpoint
--------
GET /api/v1/admin/dashboard/snapshot

Phase 2 (WAVE-19) status
------------------------
Real Django ORM aggregation. Empty DB → zeros / empty lists (honest), NO
fabricated activity. As trainer task karna shuru karega, numbers live
update honge.

Mapping notes
-------------
* "Submission" => ``tasks.Annotation`` (one trainer-submitted annotation row).
* Trainer "state" field does NOT yet exist on ``users.User`` — surfaced as
  empty string until the Step 8 schema lands. Top trainer rows render the
  email as the "name" fallback so the UI does not break.
* "Pay-hold" totals come from ``payments.PaymentHold`` (status='held') and
  ``payments.PayoutQueue`` (status='sent' today).
* Alerts: ``QualityAlert`` (status='open'), ``Dispute`` (resolved_at NULL),
  ``PayoutQueue`` (status in failed/processing).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List

from django.db.models import Count, Q, Sum
from django.utils import timezone as dj_timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.decorators import require_role


def _delta_pct(today: int, yesterday: int) -> int:
    """Return integer percent delta. None-safe: zero baseline → 0 (not div-by-zero)."""
    if not yesterday:
        return 0
    return int(round(((today - yesterday) / yesterday) * 100))


def _decimal_to_int_inr(v: Decimal) -> int:
    """Drop paise — UI expects whole INR."""
    if v is None:
        return 0
    return int(v)


def _build_dashboard_snapshot() -> Dict[str, Any]:
    """Real-data aggregation. Empty DB returns zeros / empty list.

    All counts are TODAY (IST midnight → now) for the activity tiles.
    """
    # Lazy imports — keeps this module importable in tests that stub Django.
    from core.models_alerts import QualityAlert
    from payments.models import PaymentHold, PayoutQueue
    from peer_review.models import Dispute
    from tasks.models import Annotation
    from users.models import User

    now = dj_timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    # --- submissions today / yesterday (Annotations, excluding skips) ---
    base_q = Annotation.objects.filter(was_cancelled=False)
    submissions_today = base_q.filter(created_at__date=today).count()
    submissions_yesterday = base_q.filter(created_at__date=yesterday).count()
    delta_pct = _delta_pct(submissions_today, submissions_yesterday)

    # --- active trainers (last 7d) ---
    active_trainers = (
        User.objects.filter(role='trainer', last_login__gte=week_ago).count()
    )

    # --- pay-hold + released today ---
    pay_hold_total_inr = _decimal_to_int_inr(
        PaymentHold.objects.filter(status=PaymentHold.STATUS_HELD)
        .aggregate(s=Sum('amount_inr'))['s']
    )
    pay_released_today_inr = _decimal_to_int_inr(
        PayoutQueue.objects.filter(
            status=PayoutQueue.STATUS_SENT, sent_at__date=today
        ).aggregate(s=Sum('amount_inr'))['s']
    )

    # --- top 5 trainers (most annotations today, joined w/ hold sum) ---
    top_trainers_qs = (
        User.objects.filter(role='trainer')
        .annotate(
            tasks_today=Count(
                'annotations',
                filter=Q(annotations__created_at__date=today, annotations__was_cancelled=False),
                distinct=True,
            ),
            earnings_today_inr_sum=Sum(
                'payment_holds__amount_inr',
                filter=Q(
                    payment_holds__held_at__date=today,
                    payment_holds__status__in=[
                        PaymentHold.STATUS_RELEASED,
                        PaymentHold.STATUS_HELD,
                    ],
                ),
            ),
        )
        .filter(tasks_today__gt=0)
        .order_by('-tasks_today')[:5]
    )

    top_trainers: List[Dict[str, Any]] = []
    for u in top_trainers_qs:
        name = (u.get_full_name() or u.email or f'trainer #{u.id}').strip()
        top_trainers.append(
            {
                'id': u.id,
                'name': name,
                # State is a Phase-2 / Step-8 schema add — empty until lands.
                'state': getattr(u, 'state', '') or '',
                'tasks_today': int(u.tasks_today or 0),
                'earnings_today_inr': _decimal_to_int_inr(u.earnings_today_inr_sum),
            }
        )

    # --- alerts ---
    disputes_pending = Dispute.objects.filter(resolved_at__isnull=True).count()
    quality_flags = QualityAlert.objects.filter(status=QualityAlert.STATUS_OPEN).count()
    stuck_payouts = PayoutQueue.objects.filter(
        status__in=[PayoutQueue.STATUS_FAILED, PayoutQueue.STATUS_PROCESSING]
    ).count()

    return {
        'as_of': now.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'today': {
            'submissions_count': submissions_today,
            'submissions_delta_pct': delta_pct,
            'active_trainers': active_trainers,
            'pay_hold_total_inr': pay_hold_total_inr,
            'pay_released_today_inr': pay_released_today_inr,
        },
        'top_trainers': top_trainers,
        'alerts': {
            'disputes_pending': disputes_pending,
            'quality_flags': quality_flags,
            'stuck_payouts': stuck_payouts,
        },
    }


class AdminDashboardSnapshotAPI(APIView):
    """Admin-only one-screen ops snapshot.

    Tiles: submissions today + delta, active trainers, pay-hold total,
    pay released today, alert counters. List: top 5 trainers state-wise.

    Returns 403 for non-admin authenticated users; 401 for unauthenticated.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Admin dashboard snapshot',
        description=(
            'Founder dashboard one-screen ops snapshot — submissions today, '
            'pay-hold total, top 5 trainers, alert counters. Admin role only. '
            'Real Django ORM aggregation. Empty DB returns zeros / empty list.'
        ),
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        return Response(_build_dashboard_snapshot(), status=200)
