"""TrainPlex WhatsApp Broadcast admin endpoints — Phase 1 Step 4.2-7.

URLs
----
    GET  /api/v1/admin/wa/templates          → KNOWN_TEMPLATES (en + hi labels)
    POST /api/v1/admin/wa/broadcast          → fan-out send (mocked AiSensy)
    GET  /api/v1/admin/wa/broadcast/history  → last 100 broadcast log rows

All three are admin-only via ``@require_role(['admin'])`` so the trainer /
reviewer / qa_lead roles get a clean 403 surface. The send endpoint is
rate-limited to 3 broadcasts / hour / admin to keep an overzealous admin
from blasting the entire trainer roster repeatedly during testing.

Phase 1 caveats
---------------
* The send itself is mocked — see `core/services/wa_broadcast.py` for the
  `_send_aisensy_template` swap-in point. Real call lands Week 8 once the
  AiSensy creds are in env.
* Founder personal mobile is defended at the service-layer boundary (see
  `_assert_no_founder_personal_number` in `core/services/wa_broadcast.py`);
  the broadcast cannot complete if that number leaks into params.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.wa_broadcast import (
    KNOWN_TEMPLATES,
    RATE_LIMIT_BROADCASTS_PER_HOUR,
    admin_has_room_for_broadcast,
    send_template_to_trainers,
)
from users.decorators import require_role

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/wa/templates
# ---------------------------------------------------------------------------


def _serialize_templates() -> List[Dict[str, Any]]:
    """Stable list of `{id, title_en, title_hi, description_en, description_hi}`."""
    out: List[Dict[str, Any]] = []
    for template_id, meta in KNOWN_TEMPLATES.items():
        out.append(
            {
                'id': template_id,
                'title_en': meta['title_en'],
                'title_hi': meta['title_hi'],
                'description_en': meta['description_en'],
                'description_hi': meta['description_hi'],
            }
        )
    return out


class AdminWhatsAppTemplatesAPI(APIView):
    """Admin-only list of the 5 known WA templates (with bilingual labels)."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='WA broadcast — list templates',
        description=(
            'Whitelisted WhatsApp templates the admin can broadcast in Phase 1. '
            'Each carries an en + hi title and a short description for the UI '
            'picker. Admin role only.'
        ),
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        return Response({'count': len(KNOWN_TEMPLATES), 'items': _serialize_templates()}, status=200)


# ---------------------------------------------------------------------------
# POST /api/v1/admin/wa/broadcast
# ---------------------------------------------------------------------------


class AdminWhatsAppBroadcastAPI(APIView):
    """Admin-only fan-out send.

    Body
    ----
    {
      "template_id": "bronze_passed",
      "trainer_ids": [5, 7, 12, 19],
      "custom_params": {                      # optional
        "5": {"name": "Geeta P.", "amount": 4350},
        "7": {"name": "Sunil M.", "amount": 4100}
      }
    }
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='WA broadcast — fire',
        description=(
            'Admin-only WhatsApp broadcast trigger. Rate-limited to 3 per hour '
            'per admin. Phase 1 ships with a mock AiSensy client; real send '
            'lands Week 8.'
        ),
    )
    @require_role(['admin'])
    def post(self, request, *args, **kwargs):
        data = request.data or {}
        template_id = (data.get('template_id') or '').strip()
        trainer_ids = data.get('trainer_ids') or []
        custom_params = data.get('custom_params') or {}

        # ---------- validation ----------
        if not template_id:
            return Response(
                {'error': 'template_id is required', 'field': 'template_id'},
                status=400,
            )
        if template_id not in KNOWN_TEMPLATES:
            return Response(
                {
                    'error': f'Unknown template_id: {template_id}',
                    'field': 'template_id',
                    'allowed': list(KNOWN_TEMPLATES.keys()),
                },
                status=400,
            )
        if not isinstance(trainer_ids, list) or not trainer_ids:
            return Response(
                {'error': 'trainer_ids must be a non-empty list', 'field': 'trainer_ids'},
                status=400,
            )

        # Coerce int trainer_ids (JSON often serializes them as strings).
        try:
            normalized_ids = [int(x) for x in trainer_ids]
        except (TypeError, ValueError):
            return Response(
                {'error': 'trainer_ids must contain integers only', 'field': 'trainer_ids'},
                status=400,
            )

        if not isinstance(custom_params, dict):
            return Response(
                {'error': 'custom_params must be an object', 'field': 'custom_params'},
                status=400,
            )

        # ---------- rate limit ----------
        if not admin_has_room_for_broadcast(request.user):
            return Response(
                {
                    'error': (
                        f'Rate limit hit: {RATE_LIMIT_BROADCASTS_PER_HOUR} broadcasts '
                        'per hour per admin. Try again later.'
                    ),
                    'code': 'rate_limited',
                },
                status=429,
            )

        # ---------- service call ----------
        params_per_trainer: Dict[int, Dict[str, Any]] = {}
        for k, v in custom_params.items():
            try:
                params_per_trainer[int(k)] = v if isinstance(v, dict) else {}
            except (TypeError, ValueError):
                continue

        try:
            result = send_template_to_trainers(
                template_id=template_id,
                trainer_ids=normalized_ids,
                params_per_trainer=params_per_trainer,
                admin_user=request.user,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=400)

        return Response(
            {
                'ok': True,
                'template_id': template_id,
                'counts': {
                    'sent': result['sent'],
                    'failed': result['failed'],
                    'skipped': result['skipped'],
                    'total': result['total'],
                },
                'logs': result['logs'],
            },
            status=200,
        )


# ---------------------------------------------------------------------------
# GET /api/v1/admin/wa/broadcast/history
# ---------------------------------------------------------------------------


class AdminWhatsAppBroadcastHistoryAPI(APIView):
    """Admin-only list of the last 100 broadcast log rows."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='WA broadcast — history',
        description='Last 100 WhatsApp broadcast log entries. Admin role only.',
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        from core.models_broadcast import WhatsAppBroadcastLog

        rows = list(WhatsAppBroadcastLog.objects.all()[:100])
        items: List[Dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    'id': row.id,
                    'admin_id': row.admin_id,
                    'admin_email': row.admin.email if row.admin else None,
                    'template_id': row.template_id,
                    'trainer_id': row.trainer_id_value,
                    'trainer_email': row.trainer_user.email if row.trainer_user else None,
                    'mobile_number': row.mobile_number,
                    'status': row.status,
                    'aisensy_message_id': row.aisensy_message_id,
                    'error': row.error,
                    'params': row.params,
                    'created_at': row.created_at.isoformat().replace('+00:00', 'Z'),
                }
            )
        return Response({'count': len(items), 'items': items}, status=200)
