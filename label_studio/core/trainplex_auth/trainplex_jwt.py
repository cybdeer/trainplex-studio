"""TrainPlex JWT bridge middleware (Step 3.3).

Validates TrainPlex JWT access tokens issued by ``api.trainplex.in`` and
maps them to fork Django ``User`` objects by email so the founder gets
ONE login across TrainPlex Next.js and Label Studio.

Activated by an ``Authorization: Bearer <jwt>`` header. Falls through to
existing DRF Token / Session auth if the header is missing or invalid —
strictly additive, never breaks legacy callers.
"""

from __future__ import annotations

import logging
import os

import jwt
from django.contrib.auth import get_user_model
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)
User = get_user_model()


class TrainPlexJWTAuthMiddleware(MiddlewareMixin):
    """Set ``request.user`` from a verified TrainPlex JWT.

    Configured via env:
      * ``TRAINPLEX_JWT_SECRET``   — must equal TrainPlex backend JWT_SECRET.
      * ``TRAINPLEX_JWT_ALGORITHM`` — defaults to ``HS256``.
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.secret = os.getenv("TRAINPLEX_JWT_SECRET", "")
        self.algorithm = os.getenv("TRAINPLEX_JWT_ALGORITHM", "HS256")
        if not self.secret:
            logger.warning(
                "TRAINPLEX_JWT_SECRET unset; unified-auth bridge disabled",
            )

    def process_request(self, request):  # noqa: D401 — Django MW hook
        if not self.secret:
            return None

        auth = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth.startswith("Bearer "):
            return None

        token = auth[len("Bearer "):].strip()
        if not token:
            return None

        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                options={"verify_aud": False},
            )
        except jwt.ExpiredSignatureError:
            logger.info("TrainPlex JWT expired")
            return None
        except jwt.InvalidTokenError as exc:
            logger.info("Invalid TrainPlex JWT: %s", exc)
            return None

        if payload.get("type") not in (None, "access"):
            # Only access tokens are valid for API auth; ignore refresh.
            logger.info(
                "TrainPlex JWT wrong type=%s; bridge ignored",
                payload.get("type"),
            )
            return None

        email = payload.get("email")
        if not email:
            sub = payload.get("sub", "")
            if "@" in str(sub):
                email = sub
        if not email:
            logger.info("TrainPlex JWT missing email claim")
            return None

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            logger.info(
                "TrainPlex JWT email %s not found in fork users", email,
            )
            return None
        except User.MultipleObjectsReturned:
            logger.warning(
                "TrainPlex JWT email %s ambiguous in fork users", email,
            )
            return None

        request.user = user
        request._trainplex_jwt_authenticated = True
        # Tell ``core.middleware.InactivitySessionTimeoutMiddleWare`` to skip
        # session-based last-login checks for this request — same escape hatch
        # the fork's own ``jwt_auth.middleware`` sets for SimpleJWT-issued
        # tokens. Without this the inactivity middleware would call
        # ``logout(request)`` on every JWT-only request (no Django session,
        # so ``last_login`` is always 0) and force-flip the user back to
        # AnonymousUser before DRF runs its permission checks.
        request.is_jwt = True
        return None
