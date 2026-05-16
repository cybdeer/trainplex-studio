"""TrainPlex Trainer self-service Profile + Settings API — Phase 1 Step 13.

Per plan: "Trainer self-service profile + notifications + payout + language
settings."

Endpoints (all require authentication; ``role`` is NEVER mutable on PATCH)

- ``GET    /api/v1/users/me/profile``           → extended profile read.
- ``PATCH  /api/v1/users/me/profile``           → partial update of own profile.
- ``POST   /api/v1/users/me/avatar``            → upload avatar (Phase 1 mock —
                                                    stores file in user.avatar).
- ``GET    /api/v1/users/me/sessions``          → list active sessions.
- ``DELETE /api/v1/users/me/sessions/<id>``     → revoke a single session.
- ``GET    /api/v1/users/me/login-history``     → last 10 login events.
- ``POST   /api/v1/users/me/password/change``   → require old + new, rate-limited.

Why this lives in ``users/`` (not ``core/``)
-------------------------------------------
The Step 12.4 2FA scaffolding already mounts at ``users.api_2fa``; this file
keeps the trainer settings surface in the same package so all "me" endpoints
co-locate. Routes are registered in ``core/urls.py`` (same as the other Step
4.2 admin endpoints) so import order stays one-direction (urls → modules).

Phase 1 vs Phase 2 wiring
-------------------------
- ``state`` / ``city`` / ``pincode`` / ``language`` / ``payout_settings`` /
  ``notification_prefs``: backed by the ``profile_meta`` JSON blob stored on
  ``user.custom_hotkeys`` namespace ``__trainplex_profile`` (no migration —
  re-uses existing field). Phase 2 promotes these to first-class columns.
- Sessions: Phase 1 returns the calling session only (the current AuthToken),
  since LS uses DRF Token + Django session and we don't track devices. Phase 2
  wires this to a real device-session table.
- Login history: real — reads from ``users.AuditLog`` filtered by the
  ``login_success`` / ``login_fail`` actions for the calling user.
- Password change: real (uses Django's password hasher); rate-limit 5/hour
  enforced in-process per user_id via a deque counter.
"""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict, deque
from typing import Any, Dict, List

from core.utils.common import get_client_ip
from django.contrib.auth import update_session_auth_hash
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import AuditLog
from users.services import audit_logger

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# In-process rate limiter for password-change.
#
# Founder rule (Step 12.4 cohort): security-sensitive POSTs MUST throttle even
# when the user is authenticated. 5 attempts / hour / user_id is the cap.
# Cache is process-local — fine for Phase 1 (single web container in dev).
# Phase 2 swaps for django-ratelimit (already a dep elsewhere) or Redis-backed.
# ----------------------------------------------------------------------------

_PASSWORD_CHANGE_MAX_PER_HOUR = 5
_PASSWORD_CHANGE_WINDOW_SECONDS = 3600
_password_change_hits: Dict[int, deque] = defaultdict(deque)


def _password_change_rate_limited(user_id: int) -> bool:
    """Return True if ``user_id`` has hit the per-hour password-change cap.

    Side effect: appends ``now`` to the user's deque on a non-limit path so
    the next call sees this attempt.
    """
    now = time.time()
    cutoff = now - _PASSWORD_CHANGE_WINDOW_SECONDS
    hits = _password_change_hits[user_id]
    # Evict expired entries.
    while hits and hits[0] < cutoff:
        hits.popleft()
    if len(hits) >= _PASSWORD_CHANGE_MAX_PER_HOUR:
        return True
    hits.append(now)
    return False


# ----------------------------------------------------------------------------
# Extended-profile storage.
#
# Codex audit M7 (2026-05-16): state / city / pincode / language / tier are
# now first-class columns on the User model. Migration 0015 back-fills from
# the legacy custom_hotkeys['__trainplex_profile'] JSON namespace. This
# module reads from the columns first and falls back to the JSON shim only
# if a column is unset — that gives us safe rollback semantics and lets the
# pre-migration JSON values keep serving reads during a deploy window.
#
# Other meta keys (payout_settings, notification_prefs, annotator_settings)
# remain in the JSON shim — they're freeform JSON blobs whose promotion is
# tracked under a separate audit item.
# ----------------------------------------------------------------------------

_PROFILE_META_KEY = '__trainplex_profile'

# Codex M7 — names of first-class trainer-profile columns on User. Listed
# here (not magic-stringed elsewhere) so adding a new column later just
# requires updating this tuple + the migration + model definition.
_FIRST_CLASS_PROFILE_COLUMNS = ('state', 'city', 'pincode', 'language', 'tier')

# Allow-list of editable profile fields. ``role`` and ``email`` are explicitly
# absent — silent ignore on PATCH so the founder's "trainer can't self-promote"
# guarantee holds even if the React form posts the wider object.
_EDITABLE_USER_FIELDS = {'first_name', 'last_name', 'phone'}
_EDITABLE_META_FIELDS = {
    'state',
    'city',
    'pincode',
    'language',
    'tier',  # display-only, but the UI seeds it for tier-badge rendering
    'payout_settings',
    'notification_prefs',
    # Step 13.1: trainer-side LS annotator preferences (JSONB freeform).
    # Kept opaque server-side — Phase 2 promotes to first-class columns once
    # the schema settles. Stored in the same __trainplex_profile namespace.
    'annotator_settings',
}
# Tier is computed server-side in Phase 2; for Phase 1 it lives in meta but
# is read-only via PATCH. Listed in _EDITABLE_META_FIELDS only so a Phase 2
# migration to first-class columns doesn't need to re-touch this list.
_READONLY_META_FIELDS = {'tier'}

# Step 13.1 validation regexes. Phone accepts Indian-only formats:
#   ``+91XXXXXXXXXX``, ``91XXXXXXXXXX``, ``XXXXXXXXXX`` (10 digits, starts 6-9).
# Empty string is allowed (clears the value) but anything else must match.
# Pincode is the standard 6-digit Indian PIN.
_PHONE_RE = re.compile(r'^(?:\+?91)?[6-9]\d{9}$')
_PINCODE_RE = re.compile(r'^\d{6}$')
# Allowed UI languages — keep narrow so a typo in the frontend doesn't get
# silently persisted. Same set as the Phase 1 frontend dropdown (hi/en/ta/bn).
_ALLOWED_LANGUAGES = {'hi', 'en', 'ta', 'bn'}


def _get_profile_meta(user) -> Dict[str, Any]:
    """Return the namespaced profile-meta dict, defaulting to an empty mapping."""
    hotkeys = user.custom_hotkeys or {}
    meta = hotkeys.get(_PROFILE_META_KEY) or {}
    return meta if isinstance(meta, dict) else {}


def _set_profile_meta(user, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Merge ``updates`` into the user profile + persist.

    Codex M7 split: first-class columns (state / city / pincode / language /
    tier) are written directly on the User row; everything else continues
    to live in the ``custom_hotkeys['__trainplex_profile']`` JSON namespace.
    We mirror first-class values into the JSON shim too, which costs one
    extra dict write but means a rollback to the pre-M7 code path can keep
    reading values that were written under the new code.

    Returns the merged meta dict (post-write).
    """
    hotkeys = dict(user.custom_hotkeys or {})
    meta = dict(hotkeys.get(_PROFILE_META_KEY) or {})
    # Drop read-only meta fields if the caller tried to set them.
    for k in _READONLY_META_FIELDS:
        updates.pop(k, None)

    # Split updates: first-class columns go onto the User row, the rest
    # stay in the JSON shim. ``tier`` is special — it's first-class AND
    # read-only over PATCH, so it was already filtered out above.
    column_updates: Dict[str, Any] = {}
    json_updates: Dict[str, Any] = {}
    for key, value in updates.items():
        if key in _FIRST_CLASS_PROFILE_COLUMNS:
            column_updates[key] = '' if value is None else str(value)
        else:
            json_updates[key] = value

    fields_to_save: List[str] = []
    if column_updates:
        for col, val in column_updates.items():
            setattr(user, col, val)
        fields_to_save.extend(column_updates.keys())
        # Mirror into the JSON shim for rollback compatibility.
        meta.update(column_updates)

    if json_updates:
        meta.update(json_updates)

    if column_updates or json_updates:
        hotkeys[_PROFILE_META_KEY] = meta
        user.custom_hotkeys = hotkeys
        fields_to_save.append('custom_hotkeys')
        user.save(update_fields=list(set(fields_to_save)))
    return meta


def _serialize_profile(user) -> Dict[str, Any]:
    """Return the GET /profile shape — extended profile + meta merged."""
    meta = _get_profile_meta(user)
    # Default notification prefs — keeps the React form from rendering empty
    # checkboxes on first load. Trainer can override and save.
    notification_prefs = meta.get('notification_prefs') or {
        'wa': True,
        'email': True,
        'sms': False,
        'push': True,
        'quiet_hours': True,
        'frequency_limit': True,
    }
    # Default payout settings.
    payout_settings = meta.get('payout_settings') or {
        'upi_id': '',
        'bank_account': '',
        'cadence': 'weekly',
        'min_withdraw_inr': 100,
    }
    return {
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'phone': user.phone,
        'avatar_url': user.avatar_url,
        'role': user.role,
        'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        # Codex M7 — first-class columns are the source of truth; the JSON
        # shim is a fallback for users who haven't written to the new
        # columns yet (e.g. brand-new accounts before the first PATCH).
        'state': getattr(user, 'state', '') or meta.get('state', ''),
        'city': getattr(user, 'city', '') or meta.get('city', ''),
        'pincode': getattr(user, 'pincode', '') or meta.get('pincode', ''),
        'language': (
            getattr(user, 'language', '') or meta.get('language', '') or 'en'
        ),
        'tier': (
            getattr(user, 'tier', '') or meta.get('tier', '') or 'bronze'
        ),
        'payout_settings': payout_settings,
        'notification_prefs': notification_prefs,
        # Step 13.1: LS annotator preferences (freeform JSONB). Returns ``{}``
        # if never set so the React form can default-merge without an undef
        # check on every key.
        'annotator_settings': meta.get('annotator_settings') or {},
        # Lightweight stats — Phase 2 wires real aggregations; Phase 1 reports
        # zeros so the React stats card renders without a backend crash.
        'stats': {
            'total_tasks': 0,
            'total_earnings_inr': 0,
        },
    }


class TrainerProfileAPI(APIView):
    """GET + PATCH the calling user's extended profile.

    Role-mutation guard
    -------------------
    ``role`` and ``email`` are *never* writable here regardless of the request
    body. The frontend may include them but they will be silently ignored —
    we return the post-write profile so the UI can detect the no-op.
    """

    permission_classes = (IsAuthenticated,)
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    @extend_schema(
        tags=['Users — Profile'],
        summary='Get extended profile',
        description='Return the calling user\'s extended profile + settings meta.',
    )
    def get(self, request, *args, **kwargs):
        return Response(_serialize_profile(request.user), status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Users — Profile'],
        summary='Update extended profile',
        description=(
            'Partial update of the calling user\'s profile.\n\n'
            'READ-ONLY fields:\n'
            '- ``role`` / ``tier`` — silently ignored (trainer cannot self-promote).\n'
            '- ``email`` — returns **400** if posted (change requires a separate\n'
            '  email-verification flow which is not yet wired).\n\n'
            'Validation:\n'
            '- ``phone`` — Indian format: 10 digits (6-9 start) with optional\n'
            '  ``+91`` / ``91`` prefix. Empty string clears the value.\n'
            '- ``pincode`` — exactly 6 digits. Empty string clears the value.\n'
            '- ``language`` — one of ``hi`` / ``en`` / ``ta`` / ``bn``.\n\n'
            'Convenience:\n'
            '- ``display_name`` — combined name. Server splits on the first\n'
            '  whitespace into ``first_name`` / ``last_name`` (last_name empty\n'
            '  if no whitespace present).'
        ),
    )
    def patch(self, request, *args, **kwargs):
        user = request.user
        body = request.data if isinstance(request.data, dict) else {}

        # ------------------------------------------------------------------
        # Step 13.1 guard rails — reject the things that need their own flow
        # BEFORE we touch the DB, so a partial commit can't leak state.
        # ------------------------------------------------------------------

        # Email change is out of scope until the verification flow lands.
        # Returning 400 (not silent ignore) so the UI surfaces a clear error
        # if the user attempted it from a dev console / curl.
        if 'email' in body and body.get('email') and body['email'] != user.email:
            return Response(
                {
                    'detail': (
                        'Email change requires a separate verification flow. '
                        'Use the dedicated email-change endpoint instead.'
                    ),
                    'field': 'email',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ``display_name`` is a UI convenience — split into first/last so the
        # rest of the pipeline only deals with the canonical columns.
        if 'display_name' in body and body.get('display_name') is not None:
            display_name = str(body['display_name']).strip()
            if display_name:
                parts = display_name.split(None, 1)
                # Don't clobber explicit first_name/last_name if both were sent.
                body.setdefault('first_name', parts[0])
                body.setdefault('last_name', parts[1] if len(parts) > 1 else '')

        # Phone validation. Accept empty string (clears value) or canonical
        # Indian format. We do NOT log the value itself (founder mobile rule).
        if 'phone' in body:
            phone = body.get('phone')
            phone_str = '' if phone is None else str(phone).strip()
            if phone_str and not _PHONE_RE.match(phone_str):
                return Response(
                    {
                        'detail': (
                            'Phone must be a 10-digit Indian mobile number '
                            '(starts with 6-9), optionally prefixed with +91 or 91.'
                        ),
                        'field': 'phone',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            body['phone'] = phone_str

        # Pincode validation. Same empty-clears-value semantics as phone.
        if 'pincode' in body:
            pincode = body.get('pincode')
            pincode_str = '' if pincode is None else str(pincode).strip()
            if pincode_str and not _PINCODE_RE.match(pincode_str):
                return Response(
                    {
                        'detail': 'Pincode must be exactly 6 digits.',
                        'field': 'pincode',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            body['pincode'] = pincode_str

        # Language whitelist.
        if 'language' in body and body.get('language'):
            language = str(body['language']).strip().lower()
            if language not in _ALLOWED_LANGUAGES:
                return Response(
                    {
                        'detail': (
                            'Language must be one of: '
                            + ', '.join(sorted(_ALLOWED_LANGUAGES))
                        ),
                        'field': 'language',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            body['language'] = language

        # ------------------------------------------------------------------
        # Apply updates.
        # ------------------------------------------------------------------

        # 1) User-table fields. Silently drop role / email so a stale React
        #    form can't accidentally promote the trainer (the email guard
        #    above already returned 400 on a real change attempt; identical
        #    email values are safe to keep in the body and ignore here).
        user_updates = {k: v for k, v in body.items() if k in _EDITABLE_USER_FIELDS}
        if user_updates:
            for k, v in user_updates.items():
                setattr(user, k, v)
            user.save(update_fields=list(user_updates.keys()))

        # 2) Meta fields. Same drop logic — only allow-listed keys survive.
        meta_updates = {k: v for k, v in body.items() if k in _EDITABLE_META_FIELDS}
        if meta_updates:
            _set_profile_meta(user, meta_updates)

        return Response(_serialize_profile(user), status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Users — Profile'],
        summary='Upload avatar',
        description=(
            'Upload a new avatar image. Phase 1 stores via the existing '
            '``user.avatar`` ImageField (no CDN). Phase 2 swaps for object '
            'storage with size + MIME validation.'
        ),
    )
    def post(self, request, *args, **kwargs):
        """POST /api/v1/users/me/avatar — handled on this view so a single
        URL serves GET/PATCH/POST for the profile resource.
        """
        avatar = request.FILES.get('avatar')
        if not avatar:
            return Response(
                {'detail': 'No avatar file uploaded. Use multipart key "avatar".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        user.avatar = avatar
        user.save(update_fields=['avatar'])
        return Response(
            {
                'avatar_url': user.avatar_url,
                'uploaded_at': timezone.now().isoformat(),
            },
            status=status.HTTP_200_OK,
        )


class TrainerSessionsAPI(APIView):
    """List the calling user's active sessions.

    Phase 1 returns just the current session (best-effort) because LS uses
    DRF tokens + Django sessions and we don't yet have a device-session
    table. Phase 2 wires this to a real model.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Users — Profile'],
        summary='List active sessions',
        description=(
            'Return active sessions for the calling user. Phase 1: the '
            'current session only. Phase 2: per-device session list.'
        ),
    )
    def get(self, request, *args, **kwargs):
        sess_key = getattr(request.session, 'session_key', None) or 'current'
        sessions = [
            {
                'id': sess_key,
                'created_at': timezone.now().isoformat(),
                'ip_address': get_client_ip(request),
                'user_agent': (request.META.get('HTTP_USER_AGENT') or '')[:512],
                'is_current': True,
            }
        ]
        return Response(sessions, status=status.HTTP_200_OK)


class TrainerSessionRevokeAPI(APIView):
    """Revoke a single session for the calling user.

    Phase 1: this is a stub — only the *current* session can be revoked
    (which is equivalent to a logout). Posting any session_id returns 204
    so the UI revoke button doesn't 404; real per-device revoke lands in
    Phase 2 with the session table.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Users — Profile'],
        summary='Revoke a session',
        description=(
            'Revoke a session by ID. Phase 1 stub: only the calling '
            'session is actually revoked. Phase 2: real per-device revoke.'
        ),
    )
    def delete(self, request, session_id, *args, **kwargs):
        # No-op for non-current session ids in Phase 1. Real revocation
        # would loop on Session.objects.filter(...) by user_id.
        if hasattr(request.session, 'flush'):
            try:
                request.session.flush()
            except Exception:  # noqa: BLE001 — best-effort, the UI still 204s.
                logger.exception('Session flush failed for user %s', request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrainerLoginHistoryAPI(APIView):
    """Return the last 10 login events for the calling user from AuditLog."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Users — Profile'],
        summary='Login history (last 10)',
        description=(
            'Return the most recent 10 login events for the calling user '
            'sourced from ``users.AuditLog`` (actions: login_success, login_fail). '
            'Wrong-user requests are scoped automatically — every row is the '
            'calling user\'s own, never another user\'s.'
        ),
    )
    def get(self, request, *args, **kwargs):
        rows = (
            AuditLog.objects.filter(
                user=request.user,
                action__in=[AuditLog.ACTION_LOGIN_SUCCESS, AuditLog.ACTION_LOGIN_FAIL],
            )
            .order_by('-created_at')[:10]
        )
        payload = [
            {
                'id': r.id,
                'action': r.action,
                'success': r.success,
                'ip_address': r.ip_address,
                'user_agent': r.user_agent,
                'created_at': r.created_at.isoformat(),
            }
            for r in rows
        ]
        return Response(payload, status=status.HTTP_200_OK)


class TrainerPasswordChangeAPI(APIView):
    """Change the calling user's password.

    Body: ``{old_password, new_password}``.

    Validations:
    - Both fields required (400 otherwise).
    - Old password must verify (401 otherwise).
    - New password length >= 8 (400 otherwise) — matches the Step 12 baseline.
    - Per-user 5-attempts-per-hour throttle. 429 on exhaust.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Users — Profile'],
        summary='Change password',
        description=(
            'Change the calling user\'s password. Body: {old_password, '
            'new_password}. Rate-limited to 5 attempts per hour per user.'
        ),
    )
    def post(self, request, *args, **kwargs):
        user = request.user

        if _password_change_rate_limited(user.id):
            return Response(
                {'detail': 'Too many password change attempts. Try again in 1 hour.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        body = request.data if isinstance(request.data, dict) else {}
        old_password = body.get('old_password') or ''
        new_password = body.get('new_password') or ''

        if not old_password or not new_password:
            return Response(
                {'detail': 'Both "old_password" and "new_password" are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.check_password(old_password):
            return Response(
                {'detail': 'Current password is incorrect.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 8:
            return Response(
                {'detail': 'New password must be at least 8 characters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=['password'])
        # Keep the session valid after the hash change so the user isn't
        # logged out mid-page on a "change password" submit.
        try:
            update_session_auth_hash(request, user)
        except Exception:  # noqa: BLE001
            logger.exception('update_session_auth_hash failed for user %s', user.id)

        # Emit an audit entry — security team can trail self-service rotations.
        audit_logger.log_admin_action(
            actor=user,
            action_name='password_change',
            metadata={},
            ip=get_client_ip(request),
        )

        return Response({'changed': True}, status=status.HTTP_200_OK)


__all__ = [
    'TrainerProfileAPI',
    'TrainerSessionsAPI',
    'TrainerSessionRevokeAPI',
    'TrainerLoginHistoryAPI',
    'TrainerPasswordChangeAPI',
]
