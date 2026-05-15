"""TrainPlex security middleware package (Phase 1 Step 12).

Exposes:
- Rate-limit decorators (login, API, OTP, password reset) — see ``rate_limit``.
- ``SecurityHeadersMiddleware`` — sets HSTS / X-Frame-Options / etc. on every response.
"""

from users.middleware.rate_limit import (
    ratelimit_api,
    ratelimit_login,
    ratelimit_otp,
    ratelimit_password_reset,
)
from users.middleware.security_headers import SecurityHeadersMiddleware

__all__ = [
    'SecurityHeadersMiddleware',
    'ratelimit_api',
    'ratelimit_login',
    'ratelimit_otp',
    'ratelimit_password_reset',
]
