"""TrainPlex Admin India Geographic Activity Heatmap — Phase 1 Step 4.2-6.

State-wise admin view of where the trainer base is active right now. Founder
ek nazar me dekh sakta hai konsa state zyada submissions kar raha hai, kahan
hiring chahiye, kahan se earnings flow ho rahi hain.

Per plan: "State-wise active trainers, intensity color (dark = zyada activity).
Geo-distribution at glance, hiring decisions easier."

Endpoint
--------
GET /api/v1/admin/heatmap/state-activity

Query
-----
    period  - 'today' / 'week' / 'month' (default: 'month')

Returns a JSON array — one entry per Indian state where trainers operate. The
frontend `IndiaMap` paints each polygon by `active_trainers` count; the
`StateTable` fallback ranks states for non-map viewers.

Week 4 status
-------------
No submissions / earnings / trainer-state-of-day tables exist in the fork yet
(real schema lands in Phase 2 / Step 8). For now this view returns deterministic
MOCK data via `_get_mock_state_activity()` for the 17 Indian states that match
production trainer geography. The mock data is period-aware so the UI can
demonstrate `today` / `week` / `month` filter behaviour even before real
aggregation is wired.
"""

from __future__ import annotations

from typing import Any, Dict, List

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


# ---------------------------------------------------------------------------
# MOCK data — 17 Indian states matching production trainer geography.
#
# TODO Step 4.2-6 / Phase 2 (Step 8): REPLACE with real aggregation joining
# `submissions`, `trainers`, and `payouts` tables once they land. Until then,
# the JSON contract is pinned by `test_heatmap.py` so the frontend stays
# stable across the swap.
#
# Numbers (active_trainers, submissions_count, total_earnings_inr) are
# integer-only — UI does no paise / fractional math.
#
# State codes use ISO 3166-2:IN-* short codes (e.g. 'RJ' for Rajasthan)
# so the GeoJSON / SVG layer can join cleanly without a translation table.
# ---------------------------------------------------------------------------

# Base ("month" period) numbers. The other two periods are derived by simple
# scaling so the relative ordering of states stays stable — a real query
# would obviously not just scale, but for the mock the ordering invariant
# (RJ > UP > MH > KA > GJ etc.) matches what we'd see in production.
_STATE_ACTIVITY_BASE: List[Dict[str, Any]] = [
    {'state_code': 'RJ', 'state_name': 'Rajasthan', 'active_trainers': 12,
     'submissions_count': 87, 'total_earnings_inr': 38000},
    {'state_code': 'UP', 'state_name': 'Uttar Pradesh', 'active_trainers': 9,
     'submissions_count': 76, 'total_earnings_inr': 25000},
    {'state_code': 'MH', 'state_name': 'Maharashtra', 'active_trainers': 8,
     'submissions_count': 64, 'total_earnings_inr': 22500},
    {'state_code': 'KA', 'state_name': 'Karnataka', 'active_trainers': 8,
     'submissions_count': 58, 'total_earnings_inr': 20800},
    {'state_code': 'GJ', 'state_name': 'Gujarat', 'active_trainers': 7,
     'submissions_count': 54, 'total_earnings_inr': 18500},
    {'state_code': 'PB', 'state_name': 'Punjab', 'active_trainers': 6,
     'submissions_count': 48, 'total_earnings_inr': 15200},
    {'state_code': 'TN', 'state_name': 'Tamil Nadu', 'active_trainers': 6,
     'submissions_count': 45, 'total_earnings_inr': 14200},
    {'state_code': 'MP', 'state_name': 'Madhya Pradesh', 'active_trainers': 5,
     'submissions_count': 40, 'total_earnings_inr': 12000},
    {'state_code': 'TG', 'state_name': 'Telangana', 'active_trainers': 5,
     'submissions_count': 38, 'total_earnings_inr': 11800},
    {'state_code': 'WB', 'state_name': 'West Bengal', 'active_trainers': 5,
     'submissions_count': 36, 'total_earnings_inr': 11200},
    {'state_code': 'BR', 'state_name': 'Bihar', 'active_trainers': 4,
     'submissions_count': 32, 'total_earnings_inr': 9600},
    {'state_code': 'KL', 'state_name': 'Kerala', 'active_trainers': 4,
     'submissions_count': 30, 'total_earnings_inr': 9000},
    {'state_code': 'JH', 'state_name': 'Jharkhand', 'active_trainers': 3,
     'submissions_count': 24, 'total_earnings_inr': 7200},
    {'state_code': 'OR', 'state_name': 'Odisha', 'active_trainers': 3,
     'submissions_count': 22, 'total_earnings_inr': 6800},
    {'state_code': 'AP', 'state_name': 'Andhra Pradesh', 'active_trainers': 3,
     'submissions_count': 21, 'total_earnings_inr': 6400},
    {'state_code': 'DL', 'state_name': 'Delhi', 'active_trainers': 3,
     'submissions_count': 19, 'total_earnings_inr': 6000},
    {'state_code': 'AS', 'state_name': 'Assam', 'active_trainers': 2,
     'submissions_count': 15, 'total_earnings_inr': 4500},
]


# Period scaling — keeps the contract identical regardless of period; only
# the numbers shift. Real aggregation in Phase 2 will compute these from the
# DB directly. Scaling factors are chosen so that the relative ordering of
# states is preserved across periods (so the heatmap colour ramp behaves
# consistently regardless of which filter the founder picks).
_PERIOD_SCALE = {
    'today': 0.05,   # ~ one day of a 30-day month
    'week':  0.25,   # ~ one week of a 30-day month
    'month': 1.0,
}


def _scale_int(value: int, factor: float) -> int:
    """Scale an integer by `factor`, clamped to >= 0. Returns int (no paise)."""
    return max(0, int(round(value * factor)))


def _get_mock_state_activity(period: str) -> List[Dict[str, Any]]:
    """Return mock state activity for the requested period.

    Phase 1: deterministic mock. Phase 2 (Step 8): swap for a real GROUP BY
    state aggregation over `submissions` + `payouts` joined on `trainer.state`.
    """
    factor = _PERIOD_SCALE.get(period, _PERIOD_SCALE[_DEFAULT_PERIOD])
    return [
        {
            'state_code': row['state_code'],
            'state_name': row['state_name'],
            'active_trainers': _scale_int(row['active_trainers'], factor),
            'submissions_count': _scale_int(row['submissions_count'], factor),
            'total_earnings_inr': _scale_int(row['total_earnings_inr'], factor),
        }
        for row in _STATE_ACTIVITY_BASE
    ]


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
            'period. Admin role only. NOTE: returns mock data in Phase 1 '
            '(Week 4); real DB aggregation lands in Phase 2 / Step 8.'
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
        return Response(_get_mock_state_activity(period), status=200)
