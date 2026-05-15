"""TrainPlex rate-limit decorators (Phase 1 Step 12.1).

Thin wrappers around ``django_ratelimit.decorators.ratelimit`` that codify the
four policies the founder approved for production:

================  =========================  ==========================
Decorator         Window / Limit             Key
================  =========================  ==========================
ratelimit_login            5 / 15 min        IP
ratelimit_api            100 / 1 min         IP   (default unauthed cap)
ratelimit_otp              3 / 15 min        mobile (POST 'mobile' field)
ratelimit_password_reset   3 / 1 hour        email  (POST 'email' field)
================  =========================  ==========================

State backend: Django's configured cache. With no ``CACHES`` override in
``label_studio/core/settings``, Django falls back to the in-process locmem
cache — fine for single-process dev and for tests. In production with the
Redis cache backend configured the same decorators work transparently.

NOT wired into views yet. The next agent will apply these to:
- ``users.views.user_signup`` / login view
- ``users.api.UserResetPasswordAPI``
- ``users.api.WhatsAppOTPRequestAPI``
- ``api_views.api_root`` DRF mounts

Usage::

    from users.middleware import ratelimit_login

    @ratelimit_login
    def login_view(request):
        ...

When the limit is exceeded the wrapped view raises
``django_ratelimit.exceptions.Ratelimited`` (HTTP 429). DRF views can catch
this and convert to a clean JSON response via an exception handler.
"""

from functools import wraps

from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited

# ---------------------------------------------------------------------------
# Policy constants — single source of truth for limits/windows.
# Exposed so tests + the next view-wiring agent can reference them by name.
# ---------------------------------------------------------------------------

LOGIN_RATE = '5/15m'  # 5 attempts per 15 min per IP
API_RATE = '100/m'  # 100 requests per minute per IP (unauthenticated default)
OTP_RATE = '3/15m'  # 3 OTP requests per 15 min per mobile number
PASSWORD_RESET_RATE = '3/h'  # 3 reset requests per hour per email


# ---------------------------------------------------------------------------
# Custom key functions for body-field-based limits (OTP mobile, reset email).
# django-ratelimit ships an 'ip' key out of the box, but body-keyed limits
# need a small helper.
# ---------------------------------------------------------------------------


def _post_field_key(field: str):
    """Return a callable suitable for ``ratelimit(key=...)`` that reads the
    given POST field from the incoming request.

    Falls back to ``''`` (empty bucket) when the field is missing — callers
    should still validate the field is present before relying on rate limits
    as their only abuse defence.
    """

    def _key(group, request):  # noqa: ARG001  (group is required by django-ratelimit API)
        return (request.POST.get(field) or request.data.get(field, '')) if hasattr(request, 'data') else (
            request.POST.get(field, '')
        )

    return _key


_MOBILE_KEY = _post_field_key('mobile')
_EMAIL_KEY = _post_field_key('email')


# ---------------------------------------------------------------------------
# Public decorators
# ---------------------------------------------------------------------------


def ratelimit_login(view_func):
    """5 failed login attempts per 15 min per IP.

    ``block=True`` -> the underlying decorator raises ``Ratelimited`` (-> 429)
    when the limit is hit so the view never executes and the failed-login
    counter is not double-incremented.

    We deliberately count *all* POSTs (not just failures) here — for the
    Step 12 baseline we accept that this is a tighter limit than "5 fails";
    a follow-up can use ``django-axes`` if we need fail-only counting.
    """

    return ratelimit(key='ip', rate=LOGIN_RATE, method='POST', block=True)(view_func)


def ratelimit_api(view_func):
    """100 requests per minute per IP (default for unauthenticated callers)."""

    return ratelimit(key='ip', rate=API_RATE, method='ALL', block=True)(view_func)


def ratelimit_otp(view_func):
    """3 WhatsApp OTP requests per 15 min, keyed by the ``mobile`` POST field."""

    return ratelimit(key=_MOBILE_KEY, rate=OTP_RATE, method='POST', block=True)(view_func)


def ratelimit_password_reset(view_func):
    """3 password-reset requests per hour, keyed by the ``email`` POST field."""

    return ratelimit(key=_EMAIL_KEY, rate=PASSWORD_RESET_RATE, method='POST', block=True)(view_func)


# ---------------------------------------------------------------------------
# Helper for tests + view-wiring agent: turn ``Ratelimited`` into JSON 429.
# Exposed but not auto-registered — the view-wiring agent decides where to
# install it (per-view try/except, DRF exception handler, etc.).
# ---------------------------------------------------------------------------


def handle_ratelimited(view_func):
    """Wrap a view so that ``Ratelimited`` becomes a 429 JSON response.

    Use this when the caller doesn't already have a DRF exception handler:

        @ratelimit_login
        @handle_ratelimited
        def login(request): ...
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Ratelimited:
            from django.http import JsonResponse

            return JsonResponse(
                {'detail': 'Too many requests. Please try again later.'},
                status=429,
            )

    return _wrapped


__all__ = [
    'LOGIN_RATE',
    'API_RATE',
    'OTP_RATE',
    'PASSWORD_RESET_RATE',
    'ratelimit_login',
    'ratelimit_api',
    'ratelimit_otp',
    'ratelimit_password_reset',
    'handle_ratelimited',
]
