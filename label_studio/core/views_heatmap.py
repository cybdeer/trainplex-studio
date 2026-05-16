"""TrainPlex Admin India Geographic Activity Heatmap — Phase 2 WAVE-19 real-data wiring.

State-wise admin view of where the trainer base is active right now. Founder
ek nazar me dekh sakta hai konsa state zyada submissions kar raha hai, kahan
hiring chahiye, kahan se earnings flow ho rahi hain.

Endpoint
--------
GET /api/v1/admin/heatmap/state-activity

Query
-----
    period  - 'today' / 'week' / 'month' (default: 'month')

Phase 2 (WAVE-19) status
------------------------
Real Django ORM aggregation grouped by ``users.User.state`` (if column exists).
Returns ``[]`` if no trainers have submitted in the window. The trainer
``state`` field is a Phase-2 / Step-8 schema add — until it lands we fall
back to an empty list (NOT mock).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from django.db.models import Count, Q, Sum
from django.utils import timezone as dj_timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.decorators import require_role

# Period query-param accepted values. Anything outside this set is normalised
# to the default 'month' so the UI never has to round-trip a 400 — founders on
# slow networks should always see a payload.
_VALID_PERIODS = ('today', 'week', 'month')
_DEFAULT_PERIOD = 'month'


def _period_window():
    """Return (start_datetime, label) for the requested period."""
    now = dj_timezone.now()
    return {
        'today': now - timedelta(days=1),
        'week': now - timedelta(days=7),
        'month': now - timedelta(days=30),
    }


def _trainer_has_state_column() -> bool:
    """Defensive check — return True iff ``users.User`` has a ``state`` column.

    The state column is a Phase-2 / Step-8 add; until that migration lands
    we cannot GROUP BY state, so we return ``[]`` to the UI (honest empty
    state, not mock).
    """
    from users.models import User

    try:
        User._meta.get_field('state')
        return True
    except Exception:
        return False


def _build_state_activity(period: str) -> List[Dict[str, Any]]:
    """Real-data aggregation. Empty trainer base / no state column → ``[]``."""
    if not _trainer_has_state_column():
        # No schema → no mock. Honest empty state until Phase 2 Step 8.
        return []

    from tasks.models import Annotation
    from payments.models import PaymentHold
    from users.models import User

    window = _period_window()
    start = window.get(period, window[_DEFAULT_PERIOD])

    rows = (
        User.objects.filter(role='trainer')
        .exclude(state__isnull=True)
        .exclude(state='')
        .values('state')
        .annotate(
            active_trainers=Count('id', filter=Q(last_login__gte=start), distinct=True),
            submissions_count=Count(
                'annotations',
                filter=Q(
                    annotations__created_at__gte=start,
                    annotations__was_cancelled=False,
                ),
                distinct=True,
            ),
            total_earnings_inr_sum=Sum(
                'payment_holds__amount_inr',
                filter=Q(
                    payment_holds__held_at__gte=start,
                    payment_holds__status__in=[
                        PaymentHold.STATUS_RELEASED,
                        PaymentHold.STATUS_HELD,
                    ],
                ),
            ),
        )
        .order_by('-submissions_count')
    )

    out: List[Dict[str, Any]] = []
    for r in rows:
        state = r['state'] or ''
        # Map common 2-letter codes through unchanged; full names through unchanged.
        # The UI joins on whatever string the trainer profile uses.
        earnings = r['total_earnings_inr_sum']
        out.append(
            {
                'state_code': state,
                'state_name': state,
                'active_trainers': int(r['active_trainers'] or 0),
                'submissions_count': int(r['submissions_count'] or 0),
                'total_earnings_inr': int(earnings or 0),
            }
        )
    return out


class AdminHeatmapStateActivityAPI(APIView):
    """Admin-only India geographic activity heatmap data.

    Returns a flat list — one entry per state — for the frontend to render
    either as a choropleth (`IndiaMap.tsx`) or as a sortable table
    (`StateTable.tsx`). Numbers are period-filtered via the `period` query
    parameter.

    Returns 403 for non-admin authenticated users; 401 for unauthenticated.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Admin India activity heatmap (state-wise)',
        description=(
            'Founder admin heatmap — per-state active trainer count, '
            'submissions count, and total earnings (INR) for the requested '
            'period. Admin role only. Real Django ORM aggregation. Empty '
            'trainer base → empty list.'
        ),
        parameters=[
            OpenApiParameter(
                name='period',
                description=(
                    "Aggregation window. One of 'today', 'week', 'month'. "
                    "Defaults to 'month'. Unknown values fall back to the "
                    "default rather than 400 — keeps the founder dashboard "
                    'always able to render.'
                ),
                required=False,
                type=str,
            ),
        ],
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        # Normalise the period query parameter. We deliberately silent-fall-back
        # to the default for unknown values so a stale frontend never hits a
        # 400 — the dashboard must always render.
        raw = (request.query_params.get('period') or _DEFAULT_PERIOD).strip().lower()
        period = raw if raw in _VALID_PERIODS else _DEFAULT_PERIOD
        return Response(_build_state_activity(period), status=200)
