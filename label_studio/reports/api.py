"""TrainPlex Reports + BI API — Phase 1 Step 7.

Endpoints
---------
All admin-only via ``@require_role(['admin'])``.

JSON
    GET /api/v1/admin/reports/founder-weekly
    GET /api/v1/admin/reports/leaderboard?period=daily|weekly|monthly
    GET /api/v1/admin/reports/cohorts?cohort_definition=registration_week|signup_wave|tier_promotion_month
    GET /api/v1/admin/reports/project-roi
    GET /api/v1/admin/reports/project-roi/<project_id>

PDF (streamed application/pdf)
    GET /api/v1/admin/reports/founder-weekly.pdf
    GET /api/v1/admin/reports/project-roi/<project_id>.pdf

CSV (UTF-8 BOM so Excel renders Hindi names correctly)
    GET /api/v1/admin/reports/leaderboard.csv

Phase 1 status
--------------
All four service layers return MOCK data. The shape is pinned by
``reports/tests/test_reports.py`` so the frontend stays stable across the
Phase 2 swap to real DB aggregation.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Dict, Optional

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.services import (
    cohort_analyzer,
    founder_weekly,
    leaderboard as leaderboard_service,
    pdf_renderer,
    project_roi as project_roi_service,
)
from users.decorators import require_role

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _collect_leaderboard_filters(request) -> Dict[str, Any]:
    """Extract leaderboard filter query params, returning a dict the service
    can pass directly into ``build_leaderboard``."""
    return {
        'state': request.query_params.get('state'),
        'tier': request.query_params.get('tier'),
        'language': request.query_params.get('language'),
        'project_type': request.query_params.get('project_type'),
    }


# ---------------------------------------------------------------------------
# GET /api/v1/admin/reports/founder-weekly
# ---------------------------------------------------------------------------


class FounderWeeklyAPI(APIView):
    """Admin-only founder weekly snapshot.

    Returns the full payload — top KPIs, trend lines, cohort retention,
    project ROI summary, geographic + language splits, quality KPIs.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin', 'Reports'],
        summary='Founder weekly snapshot',
        description=(
            'Comprehensive weekly snapshot — top KPIs, trend lines, cohort '
            'retention, project ROI summary, geographic + language splits, '
            'quality KPIs. Admin role only. Returns deterministic mock data '
            'in Phase 1; real DB aggregation lands in Phase 2 / Step 8.'
        ),
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        return Response(founder_weekly.build_founder_weekly_snapshot(), status=200)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/reports/founder-weekly.pdf
# ---------------------------------------------------------------------------


class FounderWeeklyPDFAPI(APIView):
    """Admin-only PDF export of the founder weekly snapshot."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin', 'Reports'],
        summary='Founder weekly snapshot (PDF)',
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        snapshot = founder_weekly.build_founder_weekly_snapshot()
        payload = pdf_renderer.render_founder_weekly_pdf(snapshot)
        resp = HttpResponse(payload, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'attachment; filename="founder-weekly-{snapshot["week_start"]}.pdf"'
        )
        resp['Content-Length'] = str(len(payload))
        return resp


# ---------------------------------------------------------------------------
# GET /api/v1/admin/reports/leaderboard
# ---------------------------------------------------------------------------


class LeaderboardAPI(APIView):
    """Admin-only trainer leaderboard.

    Query
    -----
    * ``period``        - ``daily | weekly | monthly``. Default ``weekly``.
                          Unknown values silently fall back to the default.
    * ``state``         - filter by ISO 3166-2:IN state code.
    * ``tier``          - filter by ``bronze | silver | gold``.
    * ``language``      - filter by language code.
    * ``project_type``  - filter by project type.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin', 'Reports'],
        summary='Trainer leaderboard',
        parameters=[
            OpenApiParameter(name='period', required=False, type=str),
            OpenApiParameter(name='state', required=False, type=str),
            OpenApiParameter(name='tier', required=False, type=str),
            OpenApiParameter(name='language', required=False, type=str),
            OpenApiParameter(name='project_type', required=False, type=str),
        ],
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        period = request.query_params.get('period')
        filters = _collect_leaderboard_filters(request)
        return Response(
            leaderboard_service.build_leaderboard(period, filters),
            status=200,
        )


# ---------------------------------------------------------------------------
# GET /api/v1/admin/reports/leaderboard.csv
# ---------------------------------------------------------------------------


class LeaderboardCSVAPI(APIView):
    """Admin-only CSV export of the trainer leaderboard.

    Output starts with the UTF-8 BOM (``\\ufeff``) so Excel on Windows renders
    Hindi / Tamil / Bengali trainer names correctly. Without the BOM Excel
    falls back to legacy code page and shows ``???``.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin', 'Reports'],
        summary='Trainer leaderboard (CSV)',
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        period = request.query_params.get('period')
        filters = _collect_leaderboard_filters(request)
        data = leaderboard_service.build_leaderboard(period, filters)

        buf = io.StringIO()
        # UTF-8 BOM at the very top.
        buf.write('﻿')
        writer = csv.writer(buf)
        writer.writerow([
            'rank', 'trainer_id', 'name', 'state', 'tier', 'language',
            'project_type', 'tasks_done', 'earnings_inr',
            'quality_score_pct', 'consistency_pct',
        ])
        for row in data['results']:
            writer.writerow([
                row['rank'], row['trainer_id'], row['name'], row['state'],
                row['tier'], row['language'], row['project_type'],
                row['tasks_done'], row['earnings_inr'],
                row['quality_score_pct'], row['consistency_pct'],
            ])
        body = buf.getvalue().encode('utf-8')
        resp = HttpResponse(body, content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = (
            f'attachment; filename="leaderboard-{data["period"]}.csv"'
        )
        return resp


# ---------------------------------------------------------------------------
# GET /api/v1/admin/reports/cohorts
# ---------------------------------------------------------------------------


class CohortsAPI(APIView):
    """Admin-only cohort analysis.

    Query
    -----
    * ``cohort_definition`` - ``signup_wave | registration_week |
                              tier_promotion_month``. Default ``signup_wave``.
                              Unknown values silently fall back.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin', 'Reports'],
        summary='Cohort analysis',
        parameters=[
            OpenApiParameter(name='cohort_definition', required=False, type=str),
        ],
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        cohort_definition = request.query_params.get('cohort_definition')
        return Response(
            cohort_analyzer.compute_cohort_metrics(cohort_definition),
            status=200,
        )


# ---------------------------------------------------------------------------
# GET /api/v1/admin/reports/project-roi
# GET /api/v1/admin/reports/project-roi/<project_id>
# GET /api/v1/admin/reports/project-roi/<project_id>.pdf
# ---------------------------------------------------------------------------


class ProjectROIListAPI(APIView):
    """Admin-only list of project ROIs (full table)."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin', 'Reports'],
        summary='Project ROI (all projects)',
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        return Response(
            {'results': project_roi_service.compute_all_project_roi()},
            status=200,
        )


class ProjectROIDetailAPI(APIView):
    """Admin-only single-project ROI."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin', 'Reports'],
        summary='Project ROI (single project)',
    )
    @require_role(['admin'])
    def get(self, request, project_id: int, *args, **kwargs):
        roi = project_roi_service.compute_project_roi(int(project_id))
        if roi is None:
            return Response({'error': 'project not found'}, status=404)
        return Response(roi, status=200)


class ProjectROIPDFAPI(APIView):
    """Admin-only single-project ROI PDF."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin', 'Reports'],
        summary='Project ROI (PDF)',
    )
    @require_role(['admin'])
    def get(self, request, project_id: int, *args, **kwargs):
        roi: Optional[Dict[str, Any]] = project_roi_service.compute_project_roi(int(project_id))
        if roi is None:
            return Response({'error': 'project not found'}, status=404)
        payload = pdf_renderer.render_project_roi_pdf(roi)
        resp = HttpResponse(payload, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'attachment; filename="project-roi-{roi["project_id"]}.pdf"'
        )
        resp['Content-Length'] = str(len(payload))
        return resp
