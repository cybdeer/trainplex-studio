"""Security headers middleware (Phase 1 Step 12.2 — Wave 19 W1-SEC update).

Sets a small set of defence-in-depth response headers. SINGLE-SOURCE policy:

- HSTS / X-Content-Type-Options / Referrer-Policy / Permissions-Policy are
  emitted by the host nginx snippet ``/etc/nginx/snippets/trainplex-security-headers.conf``
  so every ``/label-studio/*`` location inherits them without duplication.
  This middleware no longer sets them — when both layers added the same
  header the response carried two copies (Codex CRITICAL-7).
- ``X-Frame-Options: DENY`` IS still set here because nginx intentionally
  leaves it to the app/location: the Label Studio labelling editor needs
  SAMEORIGIN at specific paths; the app default stays DENY for everything
  else (clickjacking).

NOT touched here:
- ``Content-Security-Policy``: Label Studio already ships ``django-csp``
  (see ``django_csp`` in ``pyproject.toml`` and CSP settings in
  ``core/settings/base.py``). Overriding CSP from this middleware would
  fight with ``CSPMiddleware``.
"""


class SecurityHeadersMiddleware:
    """Add baseline security headers to every response.

    Register LAST in the ``MIDDLEWARE`` list so the headers wrap responses
    produced by every other middleware/view.
    """

    X_FRAME_OPTIONS = \x27DENY\x27

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._apply_headers(response)
        return response

    @classmethod
    def _apply_headers(cls, response):
        """Set X-Frame-Options if not already present.

        HSTS / X-Content-Type-Options / Referrer-Policy / Permissions-Policy
        are owned by the host nginx snippet (single-source). Setting them
        here too produced duplicate headers in production responses.
        """
        response.setdefault(\x27X-Frame-Options\x27, cls.X_FRAME_OPTIONS)
        return response


__all__ = [\x27SecurityHeadersMiddleware\x27]
