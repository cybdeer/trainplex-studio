"""TrainPlex 2FA API endpoints (Phase 1 Step 12.4 wire-in).

Mounted under ``/api/v1/users/me/2fa/`` (admin + qa_lead roles only).

Endpoints:

- ``POST /enroll/start``   — return a fresh secret + provisioning URI for
                              the user to scan into their authenticator app.
                              Does NOT enable 2FA on the account yet.
- ``POST /enroll/confirm`` — accept ``{secret, token}``; if the 6-digit
                              ``token`` verifies against ``secret``, persist
                              the secret and 10 fresh backup codes on the
                              user. Returns plain backup codes ONCE.
- ``POST /disable``        — accept ``{password, token}``; both must
                              verify. Clears secret + backup codes and
                              flips ``totp_enabled=False``.

Audit
-----
Both ``enroll/confirm`` and ``disable`` emit ``audit_logger.log_admin_action``
events (``2fa_enrolled`` / ``2fa_disabled``) so the security team can trail
who toggled their own 2FA state.

Login-time challenge endpoints live in ``users.views`` (``user_login`` +
``user_login_2fa_verify``) because they need access to the Django session
and the legacy ``users.functions.login`` wiring.
"""

from __future__ import annotations

import logging

from core.utils.common import get_client_ip
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.services import audit_logger, totp_handler

logger = logging.getLogger(__name__)


# Roles that are REQUIRED to set up 2FA (per founder rule, Step 12.4).
# Trainers + reviewers can't even enroll for now — the surface is admin-only.
_ALLOWED_ROLES = ('admin', 'qa_lead')


def _gate_2fa_roles(user) -> None:
    """Raise PermissionDenied if ``user`` isn't allowed to use 2FA endpoints.

    We don't use ``@require_role`` directly because the decorator's import
    path conflicts with class-method binding when also mixed with DRF
    permission_classes. Inline check keeps the dependency surface flat.
    """
    if not user or not user.is_authenticated:
        raise PermissionDenied('Login required')
    if getattr(user, 'role', None) not in _ALLOWED_ROLES:
        raise PermissionDenied(
            f'2FA is only available for roles: {", ".join(_ALLOWED_ROLES)}. '
            f'Your role: {getattr(user, "role", None)}'
        )


class TwoFactorEnrollStartAPI(APIView):
    """Step A of enrollment — hand the user a fresh secret to scan.

    The secret is NOT saved on the user yet — the frontend must echo it
    back through ``/enroll/confirm`` along with a valid 6-digit code from
    the user's authenticator. This prevents an attacker who triggers
    ``/enroll/start`` (CSRF or token-stuffing) from silently locking a
    real user out of their account.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Users — 2FA'],
        summary='Start 2FA enrollment',
        description=(
            'Generate a fresh TOTP secret + provisioning URI for the current user. '
            'Does NOT yet enable 2FA — the user must echo the secret back through '
            '/enroll/confirm with a valid 6-digit code. Admin + qa_lead only.'
        ),
    )
    def post(self, request, *args, **kwargs):
        _gate_2fa_roles(request.user)

        secret = totp_handler.generate_secret()
        provisioning_uri = totp_handler.get_provisioning_uri(request.user, secret)

        # No QR code rendering on the backend — the frontend's `qrcode`
        # client lib (already on the bundle) renders the data URL from
        # the otpauth URI. Keeps the backend dependency surface small.
        return Response(
            {
                'secret': secret,
                'provisioning_uri': provisioning_uri,
            },
            status=status.HTTP_200_OK,
        )


class TwoFactorEnrollConfirmAPI(APIView):
    """Step B of enrollment — verify a code against the candidate secret
    and persist it on the user, returning backup codes once.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Users — 2FA'],
        summary='Confirm 2FA enrollment',
        description=(
            'Verify the 6-digit code against the candidate secret. On success '
            'persist totp_secret + 10 hashed backup codes, set totp_enabled=True, '
            'and return the plain-text backup codes ONCE for the user to save.'
        ),
    )
    def post(self, request, *args, **kwargs):
        _gate_2fa_roles(request.user)

        secret = (request.data.get('secret') or '').strip()
        token = (request.data.get('token') or '').strip()

        if not secret or not token:
            return Response(
                {'detail': 'Both "secret" and "token" are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not totp_handler.verify_token(secret, token):
            return Response(
                {'detail': 'Invalid 2FA code. Please try the next code from your authenticator.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate fresh backup codes *before* the user save, so a DB
        # error doesn't leave the account half-enrolled (secret saved but
        # no codes to recover with).
        plain_codes = totp_handler.generate_backup_codes()
        hashed_codes = [totp_handler.hash_backup_code(c) for c in plain_codes]

        user = request.user
        user.totp_secret = secret
        user.totp_enabled = True
        user.backup_codes = hashed_codes
        user.save(update_fields=['totp_secret', 'totp_enabled', 'backup_codes'])

        audit_logger.log_admin_action(
            actor=user,
            action_name='2fa_enrolled',
            metadata={},
            ip=get_client_ip(request),
        )

        return Response(
            {
                'totp_enabled': True,
                # Plain codes — surfaced exactly once. UI must force the
                # user to confirm they've saved them before leaving.
                'backup_codes': plain_codes,
            },
            status=status.HTTP_200_OK,
        )


class TwoFactorDisableAPI(APIView):
    """Disable 2FA on the current user — requires BOTH password and a
    current 6-digit code.

    Why both? Either alone is enough for a stolen-laptop or stolen-phone
    attacker. Requiring both means an attacker needs the user's password
    AND a live authenticator code to weaken the account — which is
    materially the same bar as bypassing 2FA, so it doesn't open a new
    backdoor.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Users — 2FA'],
        summary='Disable 2FA',
        description=(
            'Disable 2FA on the current user. Requires the user\'s password '
            'AND a current 6-digit TOTP code (both, not either). Clears the '
            'stored secret and all unused backup codes.'
        ),
    )
    def post(self, request, *args, **kwargs):
        _gate_2fa_roles(request.user)

        password = request.data.get('password') or ''
        token = (request.data.get('token') or '').strip()
        user = request.user

        if not user.totp_enabled:
            return Response(
                {'detail': '2FA is not currently enabled on this account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password or not token:
            return Response(
                {'detail': 'Both "password" and "token" are required to disable 2FA.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.check_password(password):
            return Response(
                {'detail': 'Password is incorrect.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not totp_handler.verify_token(user.totp_secret, token):
            return Response(
                {'detail': 'Invalid 2FA code.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.totp_secret = ''
        user.totp_enabled = False
        user.backup_codes = []
        user.save(update_fields=['totp_secret', 'totp_enabled', 'backup_codes'])

        audit_logger.log_admin_action(
            actor=user,
            action_name='2fa_disabled',
            metadata={},
            ip=get_client_ip(request),
        )

        return Response({'totp_enabled': False}, status=status.HTTP_200_OK)


__all__ = [
    'TwoFactorEnrollStartAPI',
    'TwoFactorEnrollConfirmAPI',
    'TwoFactorDisableAPI',
]
