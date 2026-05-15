"""TrainPlex Admin Quality Alert Center endpoints — Phase 1 Step 4.2-8.

URLs
----
    GET  /api/v1/admin/quality-alerts          → paginated list with filters
    POST /api/v1/admin/quality-alerts/<id>/review
                                                → resolve an alert (admin verdict)
    GET  /api/v1/admin/quality-alerts/stats     → counts by severity for widget

All three are admin-only via ``@require_role(['admin'])``. The detection
itself lives in ``core/services/quality_anomaly_detector.py``; this module
is the admin-facing read/resolve surface.

Phase 1 caveats
---------------
* The detector functions are wired with mock inputs. Real call-sites from
  the peer-review submission pipeline land in Week 5.
* `submission_id` is a loose integer FK by value (no join enforced) so an
  alert about a hard-deleted submission still surfaces — important for
  the audit trail.
"""

from __future__ import annotations

import logging
from math import ceil
from typing import Any, Dict, List, Optional

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.decorators import require_role

logger = logging.getLogger(__name__)

# Hard cap so a malicious caller can't request half the table in one shot.
_PAGE_SIZE_DEFAULT = 50
_PAGE_SIZE_MAX = 200

# Allow-list — anything outside is silently ignored so a stray query param
# can't accidentally widen the filter surface.
_VALID_STATUSES = {'open', 'reviewed', 'dismissed', 'action_taken'}
_VALID_SEVERITIES = {'low', 'medium', 'high', 'critical'}
_VALID_TRIGGER_TYPES = {
    'reviewer_disagree',
    'time_anomaly',
    'duplicate_pattern',
    'reviewer_conflict',
    'cert_failed',
}

# Resolution values the POST handler accepts. ``open`` is intentionally not
# here — re-opening a resolved alert isn't a Phase 1 feature.
_VALID_RESOLUTIONS = {'reviewed', 'dismissed', 'action_taken'}


def _coerce_positive_int(value: Any, default: int, hard_max: Optional[int] = None) -> int:
    """Coerce a string/int to a positive int with default + cap.

    Negative / non-numeric / zero values fall back to ``default``. Values
    above ``hard_max`` clamp, not error — saves a 400 for a typo.
    """
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    if hard_max is not None and parsed > hard_max:
        return hard_max
    return parsed


def _serialize_alert(row) -> Dict[str, Any]:
    """Shape a `QualityAlert` row for the API response."""
    trainer = getattr(row, 'trainer', None)
    reviewed_by = getattr(row, 'reviewed_by', None)
    return {
        'id': row.id,
        'trigger_type': row.trigger_type,
        'severity': row.severity,
        'status': row.status,
        'trainer': (
            {
                'id': trainer.id if trainer else None,
                'email': getattr(trainer, 'email', '') if trainer else '',
                'role': getattr(trainer, 'role', '') if trainer else '',
            }
            if trainer is not None
            else None
        ),
        'submission_id': row.submission_id,
        'details': row.details or {},
        'reviewed_by': (
            {
                'id': reviewed_by.id if reviewed_by else None,
                'email': getattr(reviewed_by, 'email', '') if reviewed_by else '',
            }
            if reviewed_by is not None
            else None
        ),
        'reviewed_at': row.reviewed_at.isoformat().replace('+00:00', 'Z') if row.reviewed_at else None,
        'resolution_notes': row.resolution_notes or '',
        'created_at': row.created_at.isoformat().replace('+00:00', 'Z'),
    }


# ---------------------------------------------------------------------------
# GET /api/v1/admin/quality-alerts
# ---------------------------------------------------------------------------


class AdminQualityAlertsListAPI(APIView):
    """Admin-only paginated viewer for `QualityAlert` rows.

    Query params (all optional)
    ---------------------------
    * ``status``       — one of open / reviewed / dismissed / action_taken
    * ``severity``     — one of low / medium / high / critical
    * ``trigger_type`` — one of the 5 trigger enum values
    * ``trainer_id``   — integer trainer User id
    * ``page``         — 1-indexed page number, default ``1``
    * ``page_size``    — rows per page, default ``50``, capped at ``200``
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Quality alerts — list',
        description=(
            'Paginated list of quality alerts auto-flagged by the anomaly '
            'detector (time anomaly / reviewer disagreement / duplicate '
            'pattern). Filterable by status, severity, trigger type, '
            'trainer id. Admin role only.'
        ),
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        # Late import keeps this module importable in tests that stub Django.
        from core.models_alerts import QualityAlert

        qs = (
            QualityAlert.objects.all()
            .select_related('trainer', 'reviewed_by')
            .order_by('-created_at')
        )

        # ---- filters (silent-ignore on garbage so the UI never has to babysit) ----
        status_q = (request.query_params.get('status') or '').strip().lower()
        if status_q in _VALID_STATUSES:
            qs = qs.filter(status=status_q)

        severity_q = (request.query_params.get('severity') or '').strip().lower()
        if severity_q in _VALID_SEVERITIES:
            qs = qs.filter(severity=severity_q)

        trigger_q = (request.query_params.get('trigger_type') or '').strip().lower()
        if trigger_q in _VALID_TRIGGER_TYPES:
            qs = qs.filter(trigger_type=trigger_q)

        trainer_id_raw = request.query_params.get('trainer_id')
        if trainer_id_raw:
            try:
                qs = qs.filter(trainer_id=int(trainer_id_raw))
            except (TypeError, ValueError):
                # Same silent-ignore semantics — a typo doesn't break the page.
                pass

        # ---- pagination ----
        page = _coerce_positive_int(request.query_params.get('page'), default=1)
        page_size = _coerce_positive_int(
            request.query_params.get('page_size'),
            default=_PAGE_SIZE_DEFAULT,
            hard_max=_PAGE_SIZE_MAX,
        )

        total = qs.count()
        total_pages = ceil(total / page_size) if total else 0
        offset = (page - 1) * page_size
        rows = list(qs[offset:offset + page_size])

        return Response(
            {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': total_pages,
                'results': [_serialize_alert(r) for r in rows],
            },
            status=200,
        )


# ---------------------------------------------------------------------------
# POST /api/v1/admin/quality-alerts/<id>/review
# ---------------------------------------------------------------------------


class AdminQualityAlertReviewAPI(APIView):
    """Admin verdict on a single alert. Body: ``{ resolution, notes }``.

    Side effects
    ------------
    * ``status`` flips to the new resolution (one of reviewed / dismissed /
      action_taken).
    * ``reviewed_by`` set to the admin firing the POST.
    * ``reviewed_at`` set to ``now()``.
    * ``resolution_notes`` set to the body's ``notes`` (truncated to 4 KB so
      a runaway paste can't write a 1 MB row).

    Re-resolving an already-resolved alert is allowed (admin can correct
    their own verdict). The audit-trail-rich version (history per alert)
    is intentionally Phase 2 work; Phase 1 keeps a single resolution column.
    """

    _NOTES_MAX_LEN = 4096

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Quality alerts — resolve',
        description=(
            'Admin-only endpoint to resolve a quality alert. Body: '
            '`{ resolution: reviewed | dismissed | action_taken, notes }`. '
            'Sets reviewed_by + reviewed_at + status + notes on the row.'
        ),
    )
    @require_role(['admin'])
    def post(self, request, alert_id: int, *args, **kwargs):
        from django.utils import timezone

        from core.models_alerts import QualityAlert

        data = request.data or {}
        resolution = (data.get('resolution') or '').strip().lower()
        notes = data.get('notes') or ''

        if resolution not in _VALID_RESOLUTIONS:
            return Response(
                {
                    'error': (
                        'resolution must be one of: '
                        f'{", ".join(sorted(_VALID_RESOLUTIONS))}'
                    ),
                    'field': 'resolution',
                },
                status=400,
            )

        try:
            alert = QualityAlert.objects.get(id=alert_id)
        except QualityAlert.DoesNotExist:
            return Response({'error': f'QualityAlert id={alert_id} not found'}, status=404)

        if not isinstance(notes, str):
            return Response({'error': 'notes must be a string', 'field': 'notes'}, status=400)

        alert.status = resolution
        alert.reviewed_by = request.user
        alert.reviewed_at = timezone.now()
        alert.resolution_notes = notes[: self._NOTES_MAX_LEN]
        alert.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'resolution_notes'])

        logger.info(
            'TrainPlex quality alert resolved: id=%s resolution=%s by_admin=%s',
            alert.id,
            resolution,
            request.user.id if getattr(request.user, 'id', None) else None,
        )
        return Response({'ok': True, 'alert': _serialize_alert(alert)}, status=200)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/quality-alerts/stats
# ---------------------------------------------------------------------------


class AdminQualityAlertsStatsAPI(APIView):
    """Counts by severity for the admin dashboard widget.

    Response shape ::

        {
          "open": {"low": 1, "medium": 4, "high": 2, "critical": 1},
          "total_open": 8
        }

    The 4 severity keys are always present (zero-filled) so the React
    widget can render a fixed 4-cell grid without conditional logic.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Quality alerts — stats',
        description='Counts of currently-open quality alerts grouped by severity.',
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        from core.services.quality_anomaly_detector import open_alert_count_by_severity

        by_sev = open_alert_count_by_severity()
        return Response(
            {
                'open': by_sev,
                'total_open': sum(by_sev.values()),
            },
            status=200,
        )
