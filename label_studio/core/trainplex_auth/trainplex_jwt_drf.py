"""DRF adapter for the TrainPlex JWT middleware.

Plain-old REST framework auth class that returns the user previously
attached by :class:`TrainPlexJWTAuthMiddleware`. Used as the
top-priority entry in ``DEFAULT_AUTHENTICATION_CLASSES`` so DRF views
(``IsAuthenticated``, ``request.user``, ``request.auth``) honour the
unified-auth bridge before falling through to Token / Session.
"""

from __future__ import annotations

from rest_framework.authentication import BaseAuthentication


class TrainPlexJWTAuthentication(BaseAuthentication):
    """Return the user the middleware stashed, if any."""

    def authenticate(self, request):
        underlying = getattr(request, "_request", request)
        if getattr(underlying, "_trainplex_jwt_authenticated", False):
            return (underlying.user, None)
        return None
