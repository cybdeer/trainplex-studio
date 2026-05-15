"""TrainPlex Bulk Task Assign admin endpoints — Phase 1 Step 4.2-3.

URLs
----
    GET  /api/v1/admin/trainers/filter   → list trainers matching filters
    POST /api/v1/admin/tasks/bulk-assign → compute + log per-trainer plan

Founder requirement (plan quote): *"State / tier / language / cert pe filter
→ ek baar me 100 trainers ko tasks assign. Manual ek-ek checkbox khatam."*

Both endpoints are admin-only via ``@require_role(['admin'])`` so trainers /
reviewers / QA-leads get a clean 403 surface. The POST is rate-limited to
``RATE_LIMIT_BULK_ASSIGN_PER_HOUR`` (5) bursts/hr/admin so a runaway click
can't flood the queue.

Phase 1 caveats
---------------
* The trainer roster comes from the in-memory ``_TRAINER_ROSTER`` constant
  in ``core/services/bulk_assign.py`` (matches the frontend's MOCK_TRAINERS
  so the wizard + bulk-assign + WA broadcast all show the same 12 rows).
  Real ``users.User`` roster + trainer-profile fields (state / tier /
  language / cert_passed) land in Phase 2 / Step 8.
* The POST does NOT create real LS ``Task`` rows. It validates input,
  computes the per-trainer plan, logs the decision, and returns the plan
  to the admin. Phase 2 swaps :func:`_TODO_PHASE_2_assign_real_tasks` for
  the real write — same function signature.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.bulk_assign import (
    DEFAULT_TASKS_PER_TRAINER,
    DISTRIBUTE_STRATEGIES,
    RATE_LIMIT_BULK_ASSIGN_PER_HOUR,
    admin_has_room_for_bulk_assign,
    filter_trainers,
    plan_bulk_assignment,
    record_bulk_assign,
)
from users.decorators import require_role

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/trainers/filter
# ---------------------------------------------------------------------------


class AdminTrainerFilterAPI(APIView):
    """Admin-only trainer roster filter for the Bulk Assign page.

    Query parameters (all optional, all comma-separated for multi-value):
        ``state``        — e.g. ``Rajasthan,UP``
        ``tier``         — e.g. ``gold,silver``
        ``language``     — e.g. ``Hindi,Tamil``
        ``cert_passed``  — ``true`` / ``false`` / ``passed`` / ``pending``

    Multiple values within one field are OR-combined; different fields are
    AND-combined (i.e. an Rajasthan **and** gold trainer matches; an
    Rajasthan **or** Maharashtra trainer matches when both are passed).

    Returns 403 for non-admin authenticated users; 401 for unauthenticated.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Bulk Assign — filter trainer roster',
        description=(
            'Admin-only trainer filter for the Bulk Assign page. All query '
            'params optional, comma-separated for multi-value. AND across '
            'fields, OR within a field. Phase 1 returns the in-memory mock '
            'roster; Phase 2 swaps for real users.User rows.'
        ),
        parameters=[
            OpenApiParameter(name='state', required=False, type=str),
            OpenApiParameter(name='tier', required=False, type=str),
            OpenApiParameter(name='language', required=False, type=str),
            OpenApiParameter(name='cert_passed', required=False, type=str),
        ],
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        items = filter_trainers(
            state=request.query_params.get('state'),
            tier=request.query_params.get('tier'),
            language=request.query_params.get('language'),
            cert_passed=request.query_params.get('cert_passed'),
        )
        return Response({'count': len(items), 'items': items}, status=200)


# ---------------------------------------------------------------------------
# POST /api/v1/admin/tasks/bulk-assign
# ---------------------------------------------------------------------------


class AdminBulkAssignAPI(APIView):
    """Admin-only bulk task assignment to a list of trainers.

    Body
    ----
    {
      "project_id":            42,                 # required, existing Project pk
      "trainer_ids":           [5, 7, 12, 19],     # required, non-empty list of ints
      "tasks_per_trainer":     10,                 # optional, default 10
      "distribute_strategy":   "even"              # optional, default 'even'
                                                   #   one of {'even', 'tier-weighted'}
    }

    Phase 1: this validates the inputs, computes the per-trainer task plan,
    logs the decision, and returns the plan. **No real LS task rows are
    written** — that's Phase 2.

    Returns 403 for non-admins; 400 for missing or bad inputs; 429 if the
    admin has exceeded ``RATE_LIMIT_BULK_ASSIGN_PER_HOUR`` (5) bursts/hour.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Bulk Assign — plan + log task assignment',
        description=(
            'Admin-only bulk task assignment trigger. Rate-limited to 5 per '
            'hour per admin. Phase 1 returns the per-trainer plan without '
            'writing real LS task rows; real write lands Phase 2 / Step 8.'
        ),
    )
    @require_role(['admin'])
    def post(self, request, *args, **kwargs):
        data = request.data or {}
        project_id_raw = data.get('project_id')
        trainer_ids_raw = data.get('trainer_ids')
        tasks_per_trainer_raw = data.get('tasks_per_trainer', DEFAULT_TASKS_PER_TRAINER)
        distribute_strategy = (data.get('distribute_strategy') or 'even').strip()

        # -------- project_id --------
        if project_id_raw is None or project_id_raw == '':
            return Response(
                {'error': 'project_id is required', 'field': 'project_id'},
                status=400,
            )
        try:
            project_id = int(project_id_raw)
        except (TypeError, ValueError):
            return Response(
                {'error': 'project_id must be an integer', 'field': 'project_id'},
                status=400,
            )

        # Validate that the project exists. Late import keeps the module
        # importable in environments where projects.models is stubbed.
        from projects.models import Project
        if not Project.objects.filter(id=project_id).exists():
            return Response(
                {
                    'error': f'Project id={project_id} does not exist',
                    'field': 'project_id',
                },
                status=400,
            )

        # -------- trainer_ids --------
        if not isinstance(trainer_ids_raw, list) or not trainer_ids_raw:
            return Response(
                {'error': 'trainer_ids must be a non-empty list', 'field': 'trainer_ids'},
                status=400,
            )
        try:
            trainer_ids: List[int] = [int(x) for x in trainer_ids_raw]
        except (TypeError, ValueError):
            return Response(
                {'error': 'trainer_ids must contain integers only', 'field': 'trainer_ids'},
                status=400,
            )
        # Dedup while preserving order so the plan output is deterministic.
        seen = set()
        deduped: List[int] = []
        for tid in trainer_ids:
            if tid in seen:
                continue
            seen.add(tid)
            deduped.append(tid)
        trainer_ids = deduped

        # -------- tasks_per_trainer --------
        try:
            tasks_per_trainer = int(tasks_per_trainer_raw)
        except (TypeError, ValueError):
            return Response(
                {
                    'error': 'tasks_per_trainer must be an integer',
                    'field': 'tasks_per_trainer',
                },
                status=400,
            )
        if tasks_per_trainer < 0:
            return Response(
                {
                    'error': 'tasks_per_trainer must be >= 0',
                    'field': 'tasks_per_trainer',
                },
                status=400,
            )

        # -------- strategy --------
        if distribute_strategy not in DISTRIBUTE_STRATEGIES:
            return Response(
                {
                    'error': (
                        f'distribute_strategy must be one of '
                        f'{list(DISTRIBUTE_STRATEGIES)}'
                    ),
                    'field': 'distribute_strategy',
                    'allowed': list(DISTRIBUTE_STRATEGIES),
                },
                status=400,
            )

        # -------- rate limit --------
        if not admin_has_room_for_bulk_assign(request.user):
            return Response(
                {
                    'error': (
                        f'Rate limit hit: {RATE_LIMIT_BULK_ASSIGN_PER_HOUR} bulk '
                        'assigns per hour per admin. Try again later.'
                    ),
                    'code': 'rate_limited',
                },
                status=429,
            )

        # -------- service call --------
        try:
            result = plan_bulk_assignment(
                project_id=project_id,
                trainer_ids=trainer_ids,
                tasks_per_trainer=tasks_per_trainer,
                strategy=distribute_strategy,
                admin_user=request.user,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=400)

        record_bulk_assign(request.user)

        return Response(
            {
                'ok': True,
                **result,
                # Echo a top-level summary for the result drawer.
                'summary': {
                    'project_id': project_id,
                    'trainer_count': result['totals']['trainers'],
                    'total_tasks': result['totals']['tasks'],
                    'strategy': result['strategy'],
                },
            },
            status=200,
        )
