"""TrainPlex PWA endpoints — Phase 1 Step 4.3 + 4.4.

Two thin views that round out the offline + install experience:

1. ``ManifestView`` (GET ``/manifest.webmanifest``)
   ------------------------------------------------
   The Webpack/Nx build copies ``apps/labelstudio/public/manifest.webmanifest``
   into the React app's dist root, and the Django static handler already
   serves it from there in production. This Django view is a *backup*
   path that handles two awkward cases:

   - The trainer hits the Django host directly (``/manifest.webmanifest``)
     before the React app has loaded, and the staticfiles handler isn't
     mounted at the project root.
   - A reverse proxy strips the ``Content-Type: application/manifest+json``
     header that the JSON has. Browsers reject the manifest without the
     correct MIME, so this view sets it explicitly.

   Returning a server-rendered manifest also lets Phase 2 inject runtime
   values (theme color override per org branding, dynamic start_url per
   trainer's last-used surface, etc.) without rebuilding the SPA.

2. ``TrainerBatchBulkSubmitAPI`` (POST ``/api/v1/trainer/batch/bulk-submit``)
   -------------------------------------------------------------------------
   When the SW + the client-side flush wake up after the network returns,
   they could fire 10+ individual ``/submit`` POSTs back-to-back over a
   weak 2G connection. This endpoint accepts an array of queued submits
   in one request, dedupes by ``task_id`` on the server, and returns a
   per-row outcome so the client can keep / drop each IndexedDB row
   correctly.

   Trainer-only (``@require_role(['trainer'])``). 4xx on payload shape
   issues; never 5xx for a malformed entry — the bulk path needs to be
   resilient so a single bad row never strands the queue.

Phase 1 status
--------------
- Manifest: real shippable JSON (mirrors the public/manifest.webmanifest
  the React app already ships, so both paths return identical bytes).
- Bulk submit: mock acceptance — every row returns ``{ok: true}`` and
  logs the payload. Real persistence + earnings ledger writes land in
  Phase 2 / Step 8 alongside ``api_batch.TrainerBatchSubmitAPI`` (TODO).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.decorators import require_role

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Manifest contents — kept here so a misconfigured static handler can't
# 404 the install flow. Source of truth still lives in
# ``apps/labelstudio/public/manifest.webmanifest`` (the React build copies
# that file into ``dist/`` and serves it directly); this is the failover.
# ─────────────────────────────────────────────────────────────────────────────

_MANIFEST_PAYLOAD: Dict[str, Any] = {
    'name': 'TrainPlex Studio',
    'short_name': 'TrainPlex',
    'description': 'AI training platform for India',
    'start_url': '/trainer/batch',
    'display': 'standalone',
    'orientation': 'portrait-primary',
    'background_color': '#1A1A5E',
    'theme_color': '#1A1A5E',
    'icons': [
        {
            'src': '/static/icons/pwa-192.png',
            'sizes': '192x192',
            'type': 'image/png',
            'purpose': 'any',
        },
        {
            'src': '/static/icons/pwa-512.png',
            'sizes': '512x512',
            'type': 'image/png',
            'purpose': 'any',
        },
        {
            'src': '/static/icons/pwa-maskable-512.png',
            'sizes': '512x512',
            'type': 'image/png',
            'purpose': 'maskable',
        },
    ],
    'lang': 'hi-IN',
    'dir': 'auto',
    'categories': ['productivity', 'education'],
}


def manifest_view(request):
    """Serve the PWA web app manifest with the correct MIME type.

    The browser will reject a manifest served as ``application/json`` or
    ``text/plain``; only ``application/manifest+json`` is recognised by
    every modern install path (Chrome, Edge, Samsung Internet, iOS
    Safari's "Add to Home Screen"). Setting it explicitly here means the
    Django host never depends on a reverse-proxy MIME config to ship a
    working PWA install flow.

    Anonymous access — the manifest is referenced from a ``<link>`` on
    the login page too, so requiring auth would block first-time install.
    """
    body = json.dumps(_MANIFEST_PAYLOAD, ensure_ascii=False, indent=2)
    response = HttpResponse(body, content_type='application/manifest+json')
    # Long-cache the manifest — the SW handles update propagation. Each
    # deploy bumps the SW version (see ``SHELL_CACHE_VERSION`` in
    # ``apps/labelstudio/public/sw.js``) which forces a fresh fetch.
    response['Cache-Control'] = 'public, max-age=3600'
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Bulk submit endpoint.
# ─────────────────────────────────────────────────────────────────────────────

# Hard caps so a malicious / runaway client can't fan out a huge payload
# in one POST. The frontend queue keeps entries small (<1KB each); these
# limits leave plenty of headroom for legitimate sub-shift backlogs.
_MAX_BULK_ROWS = 100
_MAX_BULK_BYTES = 256 * 1024  # 256KB


class TrainerBatchBulkSubmitAPI(APIView):
    """Bulk endpoint for flushing the offline submit queue.

    Request body
    ------------
    ``{ "submits": [ { "task_id": int, ...payload } , ... ] }``

    Response
    --------
    ``{ "results": [ { "task_id": int, "ok": bool, "error"?: str } , ... ] }``

    Per-row outcomes mean a partial failure doesn't strand the whole
    batch — the client uses each ``ok`` flag to decide whether to drop
    that IndexedDB row.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='trainer-batch-bulk-submit',
        description=(
            'Bulk-flush endpoint for the PWA offline submit queue. Accepts '
            'an array of `{task_id, ...payload}` rows queued in IndexedDB '
            'while the trainer was offline. Returns a per-row outcome so '
            'the client can prune the queue selectively.'
        ),
        responses={
            200: OpenApiResponse(description='Per-row outcomes'),
            400: OpenApiResponse(description='Payload shape error'),
            401: OpenApiResponse(description='Unauthenticated'),
            403: OpenApiResponse(description='Non-trainer role'),
            413: OpenApiResponse(description='Payload too large'),
        },
    )
    @require_role(['trainer'])
    def post(self, request) -> Response:
        # Guard the payload size before reading. DRF gives us a parsed
        # body, but the underlying request still has the byte count.
        content_length = int(request.META.get('CONTENT_LENGTH') or 0)
        if content_length > _MAX_BULK_BYTES:
            return Response(
                {'error': 'payload too large', 'max_bytes': _MAX_BULK_BYTES},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        body = request.data if isinstance(request.data, dict) else {}
        submits: List[Dict[str, Any]] = body.get('submits') or []
        if not isinstance(submits, list):
            return Response(
                {'error': 'submits must be a list'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(submits) > _MAX_BULK_ROWS:
            return Response(
                {
                    'error': 'too many rows',
                    'max_rows': _MAX_BULK_ROWS,
                    'received': len(submits),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        results: List[Dict[str, Any]] = []
        # Dedup by task_id — when the SW + the client-side flush both fire
        # for the same row (race on reconnect), the second one is a no-op
        # at this layer instead of double-billing the trainer.
        seen_task_ids: set[int] = set()

        for index, row in enumerate(submits):
            if not isinstance(row, dict):
                results.append(
                    {
                        'index': index,
                        'task_id': None,
                        'ok': False,
                        'error': 'row must be an object',
                    },
                )
                continue
            task_id = row.get('task_id')
            if not isinstance(task_id, int):
                results.append(
                    {
                        'index': index,
                        'task_id': task_id,
                        'ok': False,
                        'error': 'task_id must be an int',
                    },
                )
                continue
            if task_id in seen_task_ids:
                # Idempotent at the row level — accept but mark dup.
                results.append(
                    {'index': index, 'task_id': task_id, 'ok': True, 'duplicate': True},
                )
                continue
            seen_task_ids.add(task_id)

            # Phase 1 mock — log + return ok=True. Phase 2 lands the real
            # write path that:
            #   1. Validates the trainer owns this task (via assignment).
            #   2. Persists the answer to the LS Annotation row.
            #   3. Triggers the consensus engine (peer_review).
            #   4. Books the held-payout ledger entry in payments.
            # The contract here is stable so Phase 2 is a one-file swap.
            logger.info(
                '[bulk-submit] trainer=%s task_id=%s payload_keys=%s',
                getattr(request.user, 'id', None),
                task_id,
                sorted(row.keys()),
            )
            results.append({'index': index, 'task_id': task_id, 'ok': True})

        return Response(
            {'results': results, 'accepted': sum(1 for r in results if r.get('ok'))},
            status=status.HTTP_200_OK,
        )


class TrainerBatchSubmitAPI(APIView):
    """Single-submit endpoint — the network-first path.

    Mirrors the row contract from ``TrainerBatchBulkSubmitAPI`` so the
    React layer's submit helper can use the same payload shape whether
    the device is online (this endpoint) or offline (queue → bulk-submit
    after reconnect).
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id='trainer-batch-submit',
        description=(
            'Submit a single completed task answer. Network-first path; '
            'when the device is offline the React layer parks the payload '
            'in IndexedDB and bulk-flushes via `/bulk-submit` once the '
            'connection returns.'
        ),
        responses={
            200: OpenApiResponse(description='Submit accepted'),
            400: OpenApiResponse(description='Payload shape error'),
            401: OpenApiResponse(description='Unauthenticated'),
            403: OpenApiResponse(description='Non-trainer role'),
        },
    )
    @require_role(['trainer'])
    def post(self, request) -> Response:
        body = request.data if isinstance(request.data, dict) else {}
        task_id = body.get('task_id')
        if not isinstance(task_id, int):
            return Response(
                {'error': 'task_id must be an int'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Phase 1 mock — see TrainerBatchBulkSubmitAPI.post for the
        # Phase 2 write-path roadmap.
        logger.info(
            '[submit] trainer=%s task_id=%s payload_keys=%s',
            getattr(request.user, 'id', None),
            task_id,
            sorted(body.keys()),
        )
        return Response({'ok': True, 'task_id': task_id}, status=status.HTTP_200_OK)
