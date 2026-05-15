"""TrainPlex Trainer Batch endpoint — Phase 1 Step 1.4-E.

Per plan: "10-task batch native + sticky earnings ticker."

Endpoints
---------
GET  /api/v1/trainer/batch            — return current trainer's 10-task batch
POST /api/v1/trainer/batch/refresh    — admin-only re-trigger (re-assigns the
                                         batch for the requesting admin/user).

Phase 1 status
--------------
The real batch-assignment engine (queue scheduler, tier-aware fairness, payout
ledger entries) lands in Phase 2 / Step 8 alongside the dynamic-pricing v2
write-path. Until then, GET returns a deterministic *mock* batch — 10 tasks
synthesised from the trainer's id so the founder + UI can demo the batch flow
end-to-end (tile grid, earnings ticker, completion celebration) without any DB
seeding.

Why mock vs empty DB?
- A trainer hitting `/trainer/batch` on a fresh install must see something or
  the UI tile grid never renders for QA / dogfood / demo.
- The JSON contract is pinned by `tasks/tests/test_batch.py` so the React side
  stays stable when Phase 2 swaps the mock for a real query.
- Earnings_inr values match the dynamic-pricing v1 ranges (₹5 - ₹50/task)
  documented in `core/services/pricing_v1.py` (or its equivalent — TODO
  cross-link when Phase 2 lands).

Role gate
---------
- ``GET`` is open to ``trainer`` only — reviewers and admin both see 403.
  Founder rationale: this is the trainer self-service endpoint; reviewer has
  its own queue (Phase 2) and admin has the bulk-assign workbench.
- ``POST /refresh`` is admin only — used by support / founder to nudge a
  trainer back into a working batch when their queue jams.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.decorators import require_role

logger = logging.getLogger(__name__)


# Tasks per batch. Plan locks this at 10; the ``size`` query param can shrink
# it for demos but is hard-capped at MAX_BATCH_SIZE so a curious caller can't
# fan out a huge mock payload.
DEFAULT_BATCH_SIZE = 10
MAX_BATCH_SIZE = 50


# Task-type catalog — kept short so the React tile grid renders consistent
# preview content for every mock task. Mirrors the LS template categories
# we ship in the admin gallery (see ``core/views_template_gallery.py``).
_TASK_TYPES = [
    {
        'task_type': 'image_classification',
        'preview': 'Classify the object in the image',
        'estimated_min': 1,
        'earnings_inr': 8,
        'tier': 'bronze',
    },
    {
        'task_type': 'bounding_box',
        'preview': 'Draw bounding boxes around vehicles',
        'estimated_min': 3,
        'earnings_inr': 15,
        'tier': 'silver',
    },
    {
        'task_type': 'text_sentiment',
        'preview': 'Tag the sentiment of this sentence',
        'estimated_min': 1,
        'earnings_inr': 5,
        'tier': 'bronze',
    },
    {
        'task_type': 'audio_transcription',
        'preview': 'Transcribe this 30-second audio clip',
        'estimated_min': 5,
        'earnings_inr': 25,
        'tier': 'silver',
    },
    {
        'task_type': 'ocr_kyc',
        'preview': 'Read the Aadhaar number on this card',
        'estimated_min': 2,
        'earnings_inr': 12,
        'tier': 'silver',
    },
    {
        'task_type': 'video_action',
        'preview': 'Tag the action happening in this 10s clip',
        'estimated_min': 4,
        'earnings_inr': 20,
        'tier': 'gold',
    },
    {
        'task_type': 'translation_qa',
        'preview': 'Review this Hindi → English translation',
        'estimated_min': 2,
        'earnings_inr': 10,
        'tier': 'silver',
    },
    {
        'task_type': 'named_entity',
        'preview': 'Tag entities (people / places) in the paragraph',
        'estimated_min': 3,
        'earnings_inr': 14,
        'tier': 'silver',
    },
    {
        'task_type': 'safety_review',
        'preview': 'Flag any unsafe content in this image',
        'estimated_min': 1,
        'earnings_inr': 7,
        'tier': 'bronze',
    },
    {
        'task_type': 'qa_dispute_review',
        'preview': 'Review the dispute and choose a verdict',
        'estimated_min': 5,
        'earnings_inr': 30,
        'tier': 'gold',
    },
]


def _seed_for_user(user_id: int) -> int:
    """Stable per-user offset so each trainer's mock batch looks distinct."""
    h = hashlib.sha256(str(user_id).encode('utf-8')).digest()
    return int.from_bytes(h[:4], 'big')


def _build_mock_batch(user_id: int, size: int) -> List[Dict[str, Any]]:
    """Synthesise a deterministic 10-task batch for ``user_id``.

    The first 2 tasks are marked ``in_progress`` (mock continuity for the
    UI's resume-where-you-left-off behaviour); the rest are ``pending``.
    Phase 2 replaces this with a real ORM query over the assignment ledger.
    """
    offset = _seed_for_user(user_id)
    n_types = len(_TASK_TYPES)
    batch: List[Dict[str, Any]] = []
    for i in range(size):
        tt = _TASK_TYPES[(offset + i) % n_types]
        # Mock task_id is namespaced (user-id, slot) so it's stable across
        # repeat GETs but never collides with real Task ids (which start
        # at 1 in the real LS schema).
        task_id = 9_000_000 + (user_id * 1000) + i
        status_value = 'in_progress' if i < 2 else 'pending'
        batch.append(
            {
                'task_id': task_id,
                # Mock project_id — Phase 2 swaps for the real Project FK.
                'project_id': 1_000 + (i % 5),
                'task_type': tt['task_type'],
                'preview': tt['preview'],
                'earnings_inr': tt['earnings_inr'],
                'estimated_min': tt['estimated_min'],
                'tier': tt['tier'],
                'status': status_value,
            }
        )
    return batch


def _coerce_size(raw: str | None) -> int:
    """Parse and clamp the ``size`` query parameter.

    - Missing / non-numeric → DEFAULT_BATCH_SIZE (10).
    - Negative / zero       → DEFAULT_BATCH_SIZE (10).
    - Above MAX_BATCH_SIZE  → MAX_BATCH_SIZE (50).
    """
    if raw is None:
        return DEFAULT_BATCH_SIZE
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_BATCH_SIZE
    if n <= 0:
        return DEFAULT_BATCH_SIZE
    if n > MAX_BATCH_SIZE:
        return MAX_BATCH_SIZE
    return n


class TrainerBatchAPI(APIView):
    """Return the current trainer's 10-task batch.

    Trainer role only. Returns a JSON array — one entry per task — that the
    `<BatchPage />` React component renders as a tile grid. Earnings totals
    in the sticky bottom ticker are computed client-side from this payload
    so there's exactly one number-of-truth.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Trainer'],
        summary='Get the trainer 10-task batch',
        description=(
            'Return the current trainer\'s 10-task batch tile grid. Trainer '
            'role only. Phase 1: mock data (deterministic per trainer); real '
            'assignment engine lands in Phase 2 / Step 8.'
        ),
        parameters=[
            OpenApiParameter(
                name='size',
                description=(
                    f'Tasks to return. Default {DEFAULT_BATCH_SIZE}, capped at '
                    f'{MAX_BATCH_SIZE}. Out-of-range / non-numeric values silently '
                    f'fall back to default — keeps the UI from 400-spinning.'
                ),
                required=False,
                type=int,
            ),
        ],
    )
    @require_role(['trainer'])
    def get(self, request, *args, **kwargs):
        size = _coerce_size(request.query_params.get('size'))
        batch = _build_mock_batch(request.user.id, size)
        return Response(batch, status=status.HTTP_200_OK)


class TrainerBatchRefreshAPI(APIView):
    """Force a re-assignment of the current batch (admin only, Phase 1 mock).

    In Phase 2 this calls into the assignment engine to clear the trainer's
    current batch and pull the next chunk from the project queue. For now
    it just returns a fresh mock batch with shuffled offset so the founder
    can demo the "stuck queue" recovery flow.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Trainer'],
        summary='Refresh a trainer batch (admin only)',
        description=(
            'Admin-only re-trigger of batch assignment. Body may carry '
            '{trainer_id, size}; if omitted, refreshes the calling admin\'s '
            'own batch (useful for QA). Phase 1 returns a fresh mock batch; '
            'Phase 2 wires the real assignment engine.'
        ),
    )
    @require_role(['admin'])
    def post(self, request, *args, **kwargs):
        # Admin can refresh on behalf of a trainer or for themselves.
        trainer_id = request.data.get('trainer_id') or request.user.id
        try:
            trainer_id = int(trainer_id)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'trainer_id must be an integer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        size = _coerce_size(request.data.get('size'))
        # Use a different offset bucket on refresh so the new batch looks
        # different from the previous GET. We do that by incrementing the
        # mock seed deterministically — fine for demo, replaced in Phase 2.
        batch = _build_mock_batch(trainer_id + 1, size)
        logger.info(
            'TrainerBatchRefreshAPI: admin %s refreshed batch for trainer %s (size=%d)',
            request.user.id,
            trainer_id,
            size,
        )
        return Response(
            {
                'trainer_id': trainer_id,
                'batch': batch,
                'refreshed_count': len(batch),
            },
            status=status.HTTP_200_OK,
        )


__all__ = [
    'TrainerBatchAPI',
    'TrainerBatchRefreshAPI',
    'DEFAULT_BATCH_SIZE',
    'MAX_BATCH_SIZE',
]
