"""TrainPlex peer-review API — Phase 1 Step 6.

URLs
----
    GET  /api/v1/reviewer/queue
        → reviewer's pending review assignments (role=reviewer auth)
    POST /api/v1/reviewer/submit-review
        → body { review_assignment_id, score, agreement, comment,
                  category_checks } — creates the Review row + recomputes
        consensus.
    GET  /api/v1/qa/disputes
        → QA lead's disputed tasks (role=qa_lead)
    POST /api/v1/qa/disputes/<id>/resolve
        → body { resolution, qa_notes, qa_decision? } — closes the dispute.

All endpoints enforce ``users.decorators.require_role`` so a misrouted
trainer / admin gets 403 (in addition to the frontend RoleGate).

Mock-vs-real wiring note
------------------------
* The reviewer-assigner is mocked in Phase 1 (picks from role=reviewer,
  no tier/language match yet). The real algorithm lands Phase 2.
* Payment release wiring is NOT here — Step 6.4 (next agent) handles it
  off the ConsensusResult.status flip.
"""

from __future__ import annotations

import logging
from math import ceil
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from peer_review.models import (
    ConsensusResult,
    Dispute,
    Review,
    ReviewAssignment,
)
from peer_review.services.consensus_engine import compute_consensus
from users.decorators import require_role

logger = logging.getLogger(__name__)


_PAGE_SIZE_DEFAULT = 50
_PAGE_SIZE_MAX = 200

_VALID_AGREEMENTS = {'agree', 'partial', 'disagree', 'dispute'}
_VALID_RESOLUTIONS = {
    'trainer_correct',
    'reviewer_correct',
    'ml_recheck',
    'inconclusive',
}


# ---------------------------------------------------------------------------
# small helpers — kept private; tests should hit the public surface.
# ---------------------------------------------------------------------------


def _coerce_positive_int(value: Any, default: int, hard_max: Optional[int] = None) -> int:
    """Coerce a string/int to a positive int with default + cap."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    if hard_max is not None and parsed > hard_max:
        return hard_max
    return parsed


def _coerce_score(value: Any) -> Optional[int]:
    """Coerce a score to int in [1, 5]. Returns None for invalid."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 1 or parsed > 5:
        return None
    return parsed


def _serialize_assignment(row: ReviewAssignment) -> Dict[str, Any]:
    """Shape a ReviewAssignment for the reviewer queue response.

    Trainer name / email is intentionally NOT included — blind review is
    the founder requirement. The trainer_id stays for the cooldown audit
    trail only, never rendered.
    """
    return {
        'id': row.id,
        'task_id': row.task_id,
        # NOTE: trainer_id surfaced so the frontend can compute "anonymous
        # ID" badges, but the email / name lookup is forbidden.
        'trainer_id': row.trainer_id,
        'assigned_at': row.assigned_at.isoformat().replace('+00:00', 'Z'),
        'deadline_at': row.deadline_at.isoformat().replace('+00:00', 'Z'),
        'status': row.status,
    }


def _serialize_review(rv: Review) -> Dict[str, Any]:
    return {
        'id': rv.id,
        'review_assignment_id': rv.review_assignment_id,
        'score': rv.score,
        'agreement': rv.agreement,
        'comment': rv.comment,
        'category_checks': rv.category_checks or {},
        'submitted_at': rv.submitted_at.isoformat().replace('+00:00', 'Z'),
    }


def _serialize_dispute(dp: Dispute) -> Dict[str, Any]:
    cr = dp.consensus_result
    return {
        'id': dp.id,
        'consensus_result_id': cr.id,
        'task_id': cr.task_id,
        'escalated_at': dp.escalated_at.isoformat().replace('+00:00', 'Z'),
        'consensus_status': cr.status,
        'agreed_count': cr.agreed_count,
        'disagree_count': cr.disagree_count,
        'partial_count': cr.partial_count,
        'total_reviewers': cr.total_reviewers,
        'fallback_used': cr.fallback_used,
        'qa_lead_id': dp.qa_lead_id,
        'qa_decision': dp.qa_decision or '',
        'qa_notes': dp.qa_notes or '',
        'resolved_at': dp.resolved_at.isoformat().replace('+00:00', 'Z') if dp.resolved_at else None,
        'resolution': dp.resolution or '',
    }


# ---------------------------------------------------------------------------
# GET /api/v1/reviewer/queue
# ---------------------------------------------------------------------------


class ReviewerQueueAPI(APIView):
    """Reviewer-side: list MY pending review assignments.

    Query params
    ------------
    * ``status`` — filter by status (default: pending,in_progress).
    * ``page`` / ``page_size`` — pagination (50 / cap 200).
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Reviewer'],
        summary='Reviewer queue — list my open review assignments',
        description=(
            'Returns the reviewer\'s open assignments (pending + in_progress). '
            'Submitter (trainer) name / email is intentionally NOT included — '
            'blind review is enforced.'
        ),
    )
    @require_role(['reviewer'])
    def get(self, request, *args, **kwargs):
        page = _coerce_positive_int(request.query_params.get('page'), default=1)
        page_size = _coerce_positive_int(
            request.query_params.get('page_size'),
            default=_PAGE_SIZE_DEFAULT,
            hard_max=_PAGE_SIZE_MAX,
        )

        # Default: show open work. Pass `status=done` for review history.
        status_filter = (request.query_params.get('status') or '').strip().lower()
        if status_filter == 'done':
            statuses = [ReviewAssignment.STATUS_DONE]
        elif status_filter == 'expired':
            statuses = [ReviewAssignment.STATUS_EXPIRED]
        elif status_filter == 'all':
            statuses = None
        else:
            statuses = [
                ReviewAssignment.STATUS_PENDING,
                ReviewAssignment.STATUS_IN_PROGRESS,
            ]

        qs = ReviewAssignment.objects.filter(reviewer=request.user)
        if statuses is not None:
            qs = qs.filter(status__in=statuses)
        qs = qs.order_by('deadline_at', '-assigned_at')

        total = qs.count()
        total_pages = ceil(total / page_size) if total else 0
        offset = (page - 1) * page_size
        rows = list(qs[offset: offset + page_size])

        return Response(
            {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': total_pages,
                'results': [_serialize_assignment(r) for r in rows],
            },
            status=200,
        )


# ---------------------------------------------------------------------------
# POST /api/v1/reviewer/submit-review
# ---------------------------------------------------------------------------


class ReviewerSubmitReviewAPI(APIView):
    """Reviewer-side: persist a Review against one of MY assignments.

    Body
    ----
    * ``review_assignment_id`` (int, required)
    * ``score`` (int 1-5, required)
    * ``agreement`` (one of agree / partial / disagree / dispute, required)
    * ``comment`` (str, optional)
    * ``category_checks`` (dict, optional)
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Reviewer'],
        summary='Reviewer submit-review',
        description=(
            'Persist the reviewer\'s verdict and recompute consensus for the '
            'task. Reviewer must own the assignment; second submit-review '
            'against the same assignment returns 409.'
        ),
    )
    @require_role(['reviewer'])
    def post(self, request, *args, **kwargs):
        body = request.data if isinstance(request.data, dict) else {}

        # ---- shape validation ----
        ra_id_raw = body.get('review_assignment_id')
        try:
            ra_id = int(ra_id_raw)
        except (TypeError, ValueError):
            return Response({'error': 'review_assignment_id required'}, status=400)

        score = _coerce_score(body.get('score'))
        if score is None:
            return Response({'error': 'score must be an integer in [1, 5]'}, status=400)

        agreement = (body.get('agreement') or '').strip().lower()
        if agreement not in _VALID_AGREEMENTS:
            return Response(
                {'error': f'agreement must be one of {sorted(_VALID_AGREEMENTS)}'},
                status=400,
            )

        comment = body.get('comment') or ''
        category_checks = body.get('category_checks') or {}
        if not isinstance(category_checks, dict):
            return Response({'error': 'category_checks must be an object'}, status=400)

        # ---- assignment lookup + ownership ----
        try:
            assignment = ReviewAssignment.objects.select_related('reviewer').get(id=ra_id)
        except ReviewAssignment.DoesNotExist:
            return Response({'error': 'review_assignment not found'}, status=404)

        if assignment.reviewer_id != request.user.id:
            return Response({'error': 'forbidden — not your assignment'}, status=403)

        # Idempotency guard — second submit-review against the same assignment
        # would otherwise blow up on the OneToOne unique index. Surface 409
        # so the caller can distinguish "already submitted" from validation.
        if Review.objects.filter(review_assignment=assignment).exists():
            return Response(
                {'error': 'review already submitted for this assignment'},
                status=409,
            )

        # ---- persist + recompute ----
        with transaction.atomic():
            review = Review.objects.create(
                review_assignment=assignment,
                score=score,
                agreement=agreement,
                comment=comment,
                category_checks=category_checks,
            )
            assignment.status = ReviewAssignment.STATUS_DONE
            assignment.completed_at = timezone.now()
            assignment.save(update_fields=['status', 'completed_at'])

        # Recompute consensus *outside* the atomic block — compute_consensus
        # opens its own transactions and we don't want a serialization conflict
        # to roll back the review the reviewer just wrote.
        cr = compute_consensus(assignment.task_id)

        return Response(
            {
                'ok': True,
                'review': _serialize_review(review),
                'consensus': {
                    'task_id': cr.task_id,
                    'status': cr.status,
                    'agreed_count': cr.agreed_count,
                    'disagree_count': cr.disagree_count,
                    'partial_count': cr.partial_count,
                    'total_reviewers': cr.total_reviewers,
                },
            },
            status=201,
        )


# ---------------------------------------------------------------------------
# GET /api/v1/qa/disputes
# ---------------------------------------------------------------------------


class QADisputesListAPI(APIView):
    """QA lead-side: list open disputes."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['QA'],
        summary='QA — list open disputes',
        description=(
            'Returns Dispute rows. Default shows OPEN (unresolved); pass '
            '?status=resolved to see history or ?status=all for both.'
        ),
    )
    @require_role(['qa_lead'])
    def get(self, request, *args, **kwargs):
        page = _coerce_positive_int(request.query_params.get('page'), default=1)
        page_size = _coerce_positive_int(
            request.query_params.get('page_size'),
            default=_PAGE_SIZE_DEFAULT,
            hard_max=_PAGE_SIZE_MAX,
        )

        status_q = (request.query_params.get('status') or '').strip().lower()
        qs = Dispute.objects.select_related('consensus_result', 'qa_lead')
        if status_q == 'resolved':
            qs = qs.filter(resolved_at__isnull=False)
        elif status_q != 'all':
            qs = qs.filter(resolved_at__isnull=True)
        qs = qs.order_by('-escalated_at')

        total = qs.count()
        total_pages = ceil(total / page_size) if total else 0
        offset = (page - 1) * page_size
        rows = list(qs[offset: offset + page_size])

        return Response(
            {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': total_pages,
                'results': [_serialize_dispute(dp) for dp in rows],
            },
            status=200,
        )


# ---------------------------------------------------------------------------
# POST /api/v1/qa/disputes/<id>/resolve
# ---------------------------------------------------------------------------


class QADisputeResolveAPI(APIView):
    """QA lead-side: resolve a single dispute.

    Body
    ----
    * ``resolution`` (one of trainer_correct / reviewer_correct / ml_recheck /
      inconclusive, required)
    * ``qa_notes`` (str, optional but recommended)
    * ``qa_decision`` (str, optional short summary)
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['QA'],
        summary='QA — resolve dispute',
    )
    @require_role(['qa_lead'])
    def post(self, request, dispute_id: int, *args, **kwargs):
        body = request.data if isinstance(request.data, dict) else {}
        resolution = (body.get('resolution') or '').strip().lower()
        if resolution not in _VALID_RESOLUTIONS:
            return Response(
                {'error': f'resolution must be one of {sorted(_VALID_RESOLUTIONS)}'},
                status=400,
            )
        qa_notes = body.get('qa_notes') or ''
        qa_decision = body.get('qa_decision') or ''

        try:
            dp = Dispute.objects.select_related('consensus_result').get(id=dispute_id)
        except Dispute.DoesNotExist:
            return Response({'error': 'dispute not found'}, status=404)

        if dp.resolved_at is not None:
            return Response({'error': 'dispute already resolved'}, status=409)

        dp.resolution = resolution
        dp.qa_notes = qa_notes
        dp.qa_decision = qa_decision
        dp.qa_lead = request.user
        dp.resolved_at = timezone.now()
        dp.save(update_fields=[
            'resolution', 'qa_notes', 'qa_decision', 'qa_lead', 'resolved_at',
        ])

        return Response({'ok': True, 'dispute': _serialize_dispute(dp)}, status=200)
