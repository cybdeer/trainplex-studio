"""TrainPlex Admin Dashboard widget — Phase 1 Step 4.2-1.

Founder-facing one-screen ops snapshot. Login hote hi: aaj ke submissions,
kitne pay-hold, top 5 trainers state-wise, alerts ka counter.

Endpoint
--------
GET /api/v1/admin/dashboard/snapshot

Returns a JSON snapshot the React `<DashboardWidget />` renders as KPI tiles +
a top-trainers table + alert counters. Requires the caller to have role=admin
(other roles get 403 via @require_role).

Week 4 status
-------------
No submissions/payments tables exist in the fork yet (real schema lands in
Step 8 — migration phase). For now this view returns deterministic MOCK data
via `_get_mock_dashboard_snapshot()`. The frontend can build/test against a
stable shape; real DB wiring is a swap-in at one call site.
"""

from __future__ import annotations

from datetime import datetime, timezone

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.decorators import require_role


def _get_mock_dashboard_snapshot() -> dict:
    """Return a stable mock dashboard snapshot.

    TODO Step 4.2-1: REPLACE with real aggregation queries once the
    submissions / payouts / trainers schema lands in Phase 2 (Step 8).
    Until then, this function powers the UI build against a fixed shape.

    All INR amounts are whole rupees (no paise) so the UI doesn't have to
    divide by 100 — keeps the rendering layer trivially formattable.
    """
    return {
        'as_of': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'today': {
            'submissions_count': 142,
            'submissions_delta_pct': 12,
            'active_trainers': 47,
            'pay_hold_total_inr': 4200,
            'pay_released_today_inr': 18500,
        },
        'top_trainers': [
            {
                'id': 5,
                'name': 'Geeta P.',
                'state': 'Rajasthan',
                'tasks_today': 87,
                'earnings_today_inr': 4350,
            },
            {
                'id': 7,
                'name': 'Sunil M.',
                'state': 'UP',
                'tasks_today': 82,
                'earnings_today_inr': 4100,
            },
            {
                'id': 12,
                'name': 'Anil K.',
                'state': 'Bihar',
                'tasks_today': 78,
                'earnings_today_inr': 3900,
            },
            {
                'id': 19,
                'name': 'Rekha S.',
                'state': 'MP',
                'tasks_today': 71,
                'earnings_today_inr': 3550,
            },
            {
                'id': 23,
                'name': 'Vikas T.',
                'state': 'Haryana',
                'tasks_today': 68,
                'earnings_today_inr': 3400,
            },
        ],
        'alerts': {
            'disputes_pending': 2,
            'quality_flags': 1,
            'stuck_payouts': 0,
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
            'pay-hold total, top 5 trainers state-wise, alert counters. '
            'Admin role only. NOTE: returns mock data in Phase 1 (Week 4); '
            'real DB aggregation lands in Phase 2 / Step 8.'
        ),
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        return Response(_get_mock_dashboard_snapshot(), status=200)
