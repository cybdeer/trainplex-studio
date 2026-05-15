"""Security headers middleware (Phase 1 Step 12.2).

Adds a small, sensible set of defence-in-depth response headers to every
HTTP response. Each header is only set if not already present, so an
upstream middleware / view that needs a tighter policy can still override.

Headers added:
- ``Strict-Transport-Security`` — force HTTPS for 1 year, include subdomains.
- ``X-Content-Type-Options: nosniff`` — disable MIME sniffing.
- ``X-Frame-Options: DENY`` — no embedding in iframes (clickjacking).
- ``Referrer-Policy: strict-origin-when-cross-origin`` — leak as little as
  possible to third parties while keeping internal referrer telemetry.
- ``Permissions-Policy`` — disable geolocation / mic / camera by default.

NOT touched here:
- ``Content-Security-Policy``: Label Studio already ships ``django-csp``
  (see ``django_csp`` in ``pyproject.toml`` and CSP settings in
  ``core/settings/base.py``). Overriding CSP from this middleware would
  fight with ``CSPMiddleware``. TODO: when Step 12 view-wiring lands,
  audit the existing CSP for the trainer/labelling pages and tighten
  ``script-src`` away from any ``'unsafe-inline'`` it still grants.
"""


class SecurityHeadersMiddleware:
    """Add baseline security headers to every response.

    Register LAST in the ``MIDDLEWARE`` list so the headers wrap responses
    produced by every other middleware/view.
    """

    HSTS = 'max-age=31536000; includeSubDomains'
    X_CONTENT_TYPE_OPTIONS = 'nosniff'
    X_FRAME_OPTIONS = 'DENY'
    REFERRER_POLICY = 'strict-origin-when-cross-origin'
    PERMISSIONS_POLICY = 'geolocation=(), microphone=(), camera=()'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._apply_headers(response)
        return response

    @classmethod
    def _apply_headers(cls, response):
        """Set each header only if not already present.

        Django's ``SecurityMiddleware`` already sets HSTS when the
        ``SECURE_HSTS_SECONDS`` setting is non-zero — preserving that
        upstream value avoids surprise downgrades from this middleware.
        """
        response.setdefault('Strict-Transport-Security', cls.HSTS)
        response.setdefault('X-Content-Type-Options', cls.X_CONTENT_TYPE_OPTIONS)
        response.setdefault('X-Frame-Options', cls.X_FRAME_OPTIONS)
        response.setdefault('Referrer-Policy', cls.REFERRER_POLICY)
        response.setdefault('Permissions-Policy', cls.PERMISSIONS_POLICY)
        return response


__all__ = ['SecurityHeadersMiddleware']
