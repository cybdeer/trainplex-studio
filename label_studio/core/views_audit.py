"""TrainPlex Admin Audit Log viewer endpoint — Phase 1 Step 4.2-4.

Surfaces ``users.AuditLog`` rows (written by the Step 12.3 hooks on login,
permission-change, and delete events) so the founder/admin can review the
trail from the React `<AuditLogPage />` page.

Endpoint
--------
GET /api/v1/admin/audit/log

Query parameters (all optional)
-------------------------------
- ``action``        Filter by ``AuditLog.action`` value
                    (e.g. ``login_success``, ``permission_change``, ``delete``).
- ``actor_email``   Case-insensitive substring match on ``user__email``.
- ``target_type``   Exact match on ``target_type`` (e.g. ``User``, ``Project``).
- ``success``       ``true``/``false`` (case-insensitive). Anything else is
                    ignored so a stray param can't accidentally filter.
- ``start_date``    ISO-8601 date (``YYYY-MM-DD``) — inclusive lower bound on
                    ``created_at``.
- ``end_date``      ISO-8601 date — inclusive upper bound (end-of-day).
- ``page``          1-indexed page number, default ``1``.
- ``page_size``     Rows per page, default ``50``, hard-capped at ``200`` so a
                    runaway client can't OOM the API node.

Response
--------
Paginated JSON::

    {
      "page": 1,
      "page_size": 50,
      "total": 1234,
      "total_pages": 25,
      "results": [
        {
          "id": 9001,
          "action": "login_success",
          "actor": {"id": 7, "email": "founder@x.com", "role": "admin"},
          "target_type": "User",
          "target_id": "7",
          "ip_address": "10.0.0.1",
          "user_agent": "Mozilla/5.0… (truncated to 80 chars)",
          "success": true,
          "metadata": {"...": "..."},
          "created_at": "2026-05-15T12:34:56Z"
        },
        ...
      ]
    }

Ordering: ``-created_at`` (newest first) — same as the model's default.

Access control: ``@require_role(['admin'])`` — every other role gets a 403.
The hooks that write into ``AuditLog`` deliberately don't fire for the
viewer GET, so admins reading the log don't pollute it.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timezone
from math import ceil
from typing import Any, Dict, Optional

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.decorators import require_role
from users.models import AuditLog

logger = logging.getLogger(__name__)

# Hard cap so a malicious / buggy caller can't request half the table.
_PAGE_SIZE_DEFAULT = 50
_PAGE_SIZE_MAX = 200

# user_agent is shown inline in the table; the full string is in metadata if
# the admin wants it. Keep this short so wide UA strings don't blow the row.
_UA_DISPLAY_LEN = 80


def _parse_iso_date(value: str) -> Optional[datetime]:
    """Parse ``YYYY-MM-DD`` to a UTC-aware datetime, or return ``None``.

    We accept the bare date form only — full ISO-8601 with time is intentionally
    out of scope so the filter UI stays a date-picker, not a timestamp picker.
    """
    if not value:
        return None
    try:
        # ``date.fromisoformat`` rejects garbage like ``2026/05/15`` cleanly.
        d = datetime.fromisoformat(value).date()
    except ValueError:
        return None
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _parse_bool(value: str) -> Optional[bool]:
    """Convert a query-string truthy/falsy string to a bool, or ``None``."""
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in ('true', '1', 'yes'):
        return True
    if lowered in ('false', '0', 'no'):
        return False
    return None


def _coerce_positive_int(value: str, default: int, hard_max: Optional[int] = None) -> int:
    """Coerce a query-param string to a positive int with a default + cap.

    Negative / non-numeric / zero values fall back to ``default``. Values above
    ``hard_max`` are clamped, never silently rounded up.
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


def _serialize_row(row: AuditLog) -> Dict[str, Any]:
    """Shape one ``AuditLog`` row for the API response."""
    actor: Optional[Dict[str, Any]] = None
    if row.user_id is not None:
        # Avoid an extra query per row — we ``select_related`` in the view.
        u = row.user
        actor = {
            'id': u.id if u else None,
            'email': getattr(u, 'email', '') if u else '',
            'role': getattr(u, 'role', '') if u else '',
        }

    ua = row.user_agent or ''
    return {
        'id': row.id,
        'action': row.action,
        'actor': actor,
        'target_type': row.target_type or '',
        'target_id': row.target_id or '',
        'ip_address': row.ip_address,
        'user_agent': ua[:_UA_DISPLAY_LEN] + ('…' if len(ua) > _UA_DISPLAY_LEN else ''),
        'success': bool(row.success),
        'metadata': row.metadata or {},
        'created_at': row.created_at.isoformat().replace('+00:00', 'Z'),
    }


class AdminAuditLogAPI(APIView):
    """Admin-only paginated viewer for the audit trail.

    Filters compose with AND semantics — passing ``action=login_fail`` AND
    ``success=true`` returns the (likely empty) overlap, never a union.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Admin audit log viewer',
        description=(
            'Paginated list of audit events (login, role-change, delete, '
            'admin-action). Filterable by action, actor email, target type, '
            'success, and date range. Admin role only — every other role '
            'gets a 403. Newest events first.'
        ),
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        qs = AuditLog.objects.all().select_related('user').order_by('-created_at')

        # --------------- Filters ---------------
        action = request.query_params.get('action') or ''
        if action:
            qs = qs.filter(action=action)

        actor_email = request.query_params.get('actor_email') or ''
        if actor_email:
            # Substring + case-insensitive so the admin can search by domain
            # or by name fragment without knowing the full email.
            qs = qs.filter(user__email__icontains=actor_email)

        target_type = request.query_params.get('target_type') or ''
        if target_type:
            qs = qs.filter(target_type=target_type)

        success_raw = request.query_params.get('success')
        success = _parse_bool(success_raw) if success_raw is not None else None
        if success is not None:
            qs = qs.filter(success=success)

        start_dt = _parse_iso_date(request.query_params.get('start_date') or '')
        if start_dt is not None:
            qs = qs.filter(created_at__gte=start_dt)

        end_dt = _parse_iso_date(request.query_params.get('end_date') or '')
        if end_dt is not None:
            # End-date is inclusive — bump to end-of-day so events that happened
            # at 23:59 on the chosen day are still returned.
            end_of_day = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            qs = qs.filter(created_at__lte=end_of_day)

        # --------------- Pagination ---------------
        page = _coerce_positive_int(request.query_params.get('page') or '', default=1)
        page_size = _coerce_positive_int(
            request.query_params.get('page_size') or '',
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
                'results': [_serialize_row(r) for r in rows],
            },
            status=200,
        )
