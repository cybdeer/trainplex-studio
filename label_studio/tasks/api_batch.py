"""TrainPlex Trainer Batch endpoint — WAVE-19 BATCH-LEVEL grouping (founder fix).

Per founder screenshot reconciliation (2026-05-16): the trainer landing page
must show 1 card per PROJECT (= 1 batch series of 10 tasks), NOT 10 cards
(one per individual task).  Mirror the design of ``/trainer/tasks`` so the
trainer sees "Available batches" cards with theme + pay/batch + available
batches count, just like the existing TrainPlex Next.js page.

Endpoints
---------
GET  /api/v1/trainer/batch
    Returns ``{results: [BatchSummary], closed_for_user: bool, reason?: str}``.
    Each summary = one project's next 10-task chunk, plus how many more
    chunks remain.

POST /api/v1/trainer/batch/<batch_id>/claim
    Reserve the next 10 un-labeled task IDs in the given project. Returns
    the task_id list + ``first_task_id`` so the SPA can router.push to
    ``/trainer/task/<first_task_id>``.

POST /api/v1/trainer/batch/refresh
    Admin-only refresh trigger (preserved from Phase 1).

Allowlist gate (tonight only)
-----------------------------
The trainer batch surface is closed for everyone except the ceo email and
admin/superuser until founder green-lights wider rollout. Other trainers
see ``closed_for_user=true`` so the SPA shows a "Coming soon" gate.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tasks.models import Annotation, Task
from users.decorators import require_role
from users.decorators.require_role import _trainer_gate_open

logger = logging.getLogger(__name__)


# Tasks per batch. Plan locks this at 10; matches /trainer/tasks contract.
DEFAULT_BATCH_SIZE = 10
MAX_BATCH_SIZE = 50

# Default INR per batch (10 tasks @ ₹5/task = ₹50/batch). Matches the
# founder's screenshot "Pay/batch ₹50". Overrides land via project
# metadata in the Phase 2 pricing engine.
DEFAULT_PAY_INR_PER_BATCH = 50


# --------------------------------------------------------------------------
# Theme inference
# --------------------------------------------------------------------------

# Map fork project titles ("Pilot Batch — Hindi Culture") to the chip slug
# the SPA expects ("culture"). Slugs match THEME_LABELS in the existing
# /trainer/tasks page so the chip filter and emoji palette are shared.
_THEME_KEYWORDS = {
    "hinglish": "codeswitching",
    "codeswitching": "codeswitching",
    "culture": "culture",
    "cultural": "culture",
    "daily life": "daily_life",
    "daily": "daily_life",
    "regional": "regional",
    "region": "regional",
    "sensitive": "sensitive",
}


def _infer_theme(project) -> str:
    """Derive a chip slug from the project title.

    Example: ``Pilot Batch — Hindi Culture`` -> ``culture``.
    Returns ``"general"`` if no keyword matches so the chip filter still
    shows the card under "All themes".
    """
    title = (project.title or "").lower()
    for kw, slug in _THEME_KEYWORDS.items():
        if kw in title:
            return slug
    return "general"


def _project_code(project) -> str:
    """Deterministic short code surfaced on each card top-line.

    Format: ``RLHF-2026-008`` for project id 8. Stable, sortable, and
    safe to copy/paste into Slack threads.
    """
    return f"RLHF-2026-{project.id:03d}"


# --------------------------------------------------------------------------
# Allowlist + claim helpers
# --------------------------------------------------------------------------


def _list_available_batches(user) -> List[Dict[str, Any]]:
    """Return batch-level summaries grouped by project.

    Each entry corresponds to ONE project. ``task_count`` is the size of
    the NEXT claimable batch (≤ 10); ``available_batches`` is how many
    full + partial chunks of 10 still exist in that project. The card
    UI shows both numbers (e.g. "Batch 10 tasks · Available 5 batches").
    """
    from projects.models import Project

    out: List[Dict[str, Any]] = []
    project_qs = Project.objects.all().order_by("id")
    for project in project_qs:
        unlabeled_count = Task.objects.filter(project=project, is_labeled=False).count()
        if unlabeled_count == 0:
            continue

        available_batches = (unlabeled_count + DEFAULT_BATCH_SIZE - 1) // DEFAULT_BATCH_SIZE

        active_in_project = Annotation.objects.filter(
            task__project=project,
            completed_by=user,
            was_cancelled=False,
        ).count()

        out.append(
            {
                "batch_id": f"prj-{project.id}-current",
                "project_id": project.id,
                "project_code": _project_code(project),
                "theme": _infer_theme(project),
                "title": project.title or "Untitled project",
                "task_count": min(DEFAULT_BATCH_SIZE, unlabeled_count),
                "pay_inr": DEFAULT_PAY_INR_PER_BATCH,
                "pay_paise_per_batch": DEFAULT_PAY_INR_PER_BATCH * 100,
                "available_batches": available_batches,
                "tier": getattr(user, "tier", None) or "bronze",
                "status": "in_progress" if active_in_project > 0 else "available",
                "deadline": None,
            }
        )
    return out


def _claim_next_task_ids(project_id: int, size: int = DEFAULT_BATCH_SIZE) -> List[int]:
    """Return the next ``size`` un-labeled task IDs in a project.

    Used by ``POST /trainer/batch/<batch_id>/claim``. Phase 2 Step 8 will
    layer a real reservation ledger on top; for tonight we surface the
    next-ten queryset deterministically by ``id``.
    """
    return list(
        Task.objects.filter(project_id=project_id, is_labeled=False)
        .order_by("id")
        .values_list("id", flat=True)[:size]
    )


# --------------------------------------------------------------------------
# API views
# --------------------------------------------------------------------------


class TrainerBatchAPI(APIView):
    """Return the batch-level landing for the current trainer."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Trainer"],
        summary="List available batches",
        description=(
            "Return one BatchSummary per fork project that still has "
            "un-labeled tasks. Each summary = a 10-task batch the trainer "
            "can claim. Gated behind the tonight-only allowlist; "
            "non-allowlisted trainers receive closed_for_user=true."
        ),
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        if not _trainer_gate_open(user):
            return Response(
                {
                    "results": [],
                    "closed_for_user": True,
                    "reason": "Aapke liye abhi batch tayar nahi. Jaldi available hoga.",
                },
                status=status.HTTP_200_OK,
            )
        try:
            batches = _list_available_batches(user)
        except Exception:  # pragma: no cover — never 5xx the landing page
            logger.exception("TrainerBatchAPI: list_available_batches failed")
            batches = []
        return Response(
            {"results": batches, "closed_for_user": False},
            status=status.HTTP_200_OK,
        )


class TrainerBatchClaimAPI(APIView):
    """Reserve the next 10 un-labeled tasks in a project (a "batch")."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Trainer"],
        summary="Claim a 10-task batch",
        description=(
            "Reserve the next 10 un-labeled task IDs in the project "
            "referenced by ``batch_id`` (format prj-<project_id>-current). "
            "Returns ``{batch_id, task_ids, first_task_id}`` so the SPA "
            "can navigate the trainer into the labeling flow."
        ),
    )
    def post(self, request, batch_id: str, *args, **kwargs):
        user = request.user
        if not _trainer_gate_open(user):
            return Response(
                {
                    "detail": "Aapke liye abhi batch tayar nahi.",
                    "closed_for_user": True,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            parts = batch_id.split("-")
            project_id = int(parts[1])
        except (IndexError, ValueError):
            return Response(
                {"detail": "Invalid batch_id. Expected prj-<project_id>-current."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task_ids = _claim_next_task_ids(project_id, DEFAULT_BATCH_SIZE)
        if not task_ids:
            return Response(
                {"detail": "No tasks available in this batch right now."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "batch_id": batch_id,
                "project_id": project_id,
                "task_ids": task_ids,
                "first_task_id": task_ids[0],
            },
            status=status.HTTP_200_OK,
        )


class TrainerBatchRefreshAPI(APIView):
    """Admin-only batch refresh trigger (preserved from Phase 1).

    The Phase 1 mock-batch builder is replaced by the real
    ``_list_available_batches`` helper above; the endpoint still returns
    ``{trainer_id, batches, refreshed_count}`` so existing admin clients
    keep working.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Trainer"],
        summary="Refresh batch list (admin only)",
    )
    @require_role(["admin"])
    def post(self, request, *args, **kwargs):
        from users.models import User  # local import — avoids app-load cycles

        trainer_id = request.data.get("trainer_id") or request.user.id
        try:
            trainer_id = int(trainer_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "trainer_id must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            trainer = User.objects.get(id=trainer_id)
        except User.DoesNotExist:
            return Response(
                {"detail": f"trainer {trainer_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            batches = _list_available_batches(trainer)
        except Exception:  # pragma: no cover
            logger.exception("TrainerBatchRefreshAPI: build failed")
            batches = []
        logger.info(
            "TrainerBatchRefreshAPI: admin %s refreshed batches for trainer %s",
            request.user.id,
            trainer_id,
        )
        return Response(
            {
                "trainer_id": trainer_id,
                "batches": batches,
                "refreshed_count": len(batches),
            },
            status=status.HTTP_200_OK,
        )


class TrainerTaskSkipAPI(APIView):
    """Skip a single task — trainer-initiated, logged for audit.

    WAVE-19 / W2-URLS (2026-05-16)
    ------------------------------
    POST /api/v1/trainer/task/<task_id>/skip
    Body: {"reason": "<short reason>"}
    Trainer may skip a task they cannot label (e.g. ambiguous content,
    language gap, unsafe). Minimum Phase 1 behaviour: validate the task
    exists, log the skip via the audit pipeline, and return 200 so the
    PWA can advance to the next task without retrying.
    """

    permission_classes = (IsAuthenticated,)

    @require_role(["trainer", "admin"])
    def post(self, request, task_id):
        from tasks.models import Task as _Task

        reason = (request.data or {}).get("reason", "no_reason")
        task = _Task.objects.filter(id=task_id).first()
        if not task:
            return Response({"detail": "Task not found"}, status=status.HTTP_404_NOT_FOUND)
        logger.info(
            "TrainerTaskSkipAPI: trainer=%s task=%s reason=%s",
            getattr(request.user, "id", None),
            task_id,
            reason,
        )
        return Response(
            {"task_id": task_id, "skipped": True, "reason": reason},
            status=status.HTTP_200_OK,
        )


__all__ = [
    "TrainerBatchAPI",
    "TrainerBatchClaimAPI",
    "TrainerBatchRefreshAPI",
    "TrainerTaskSkipAPI",
    "DEFAULT_BATCH_SIZE",
    "MAX_BATCH_SIZE",
    "DEFAULT_PAY_INR_PER_BATCH",
]
