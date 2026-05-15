"""Partial-login token helper (Phase 1 Step 12.4 — 2FA wire-in).

After password verification succeeds for a user with ``totp_enabled=True``,
we don't fully log them in yet — we hand back a short-lived signed token
that the 2FA-challenge view will redeem for a full session.

The token is a JSON-serialized payload signed via Django's
``TimestampSigner``. It's ~150 bytes and binds:

- ``user_id`` — the account in flight
- ``step``  — always ``'2fa_pending'`` (lets us reuse the signer for
  future multi-step flows without a token type collision)

Expiry is 5 minutes — enough for a user to fetch a code from their
authenticator app, not so long that a leaked token lets an attacker
walk past 2FA hours later. Token is single-step and stateless: there's
no DB lookup, so an attacker who steals one before it expires only gets
to bypass 2FA on this one user this one time.

We picked ``django.core.signing`` over PyJWT because:
- it's already in Django stdlib (no new dep)
- ``TimestampSigner.unsign(max_age=...)`` gives us expiry for free
- the secret is ``settings.SECRET_KEY`` which is rotation-aware
"""

from __future__ import annotations

from typing import Optional

from django.core import signing

# 5 minutes — matches the 2FA-challenge UX window. Authenticator codes
# rotate every 30s so giving 5 min covers slow typing + a code-rollover.
_TOKEN_MAX_AGE_SECONDS = 300

_SALT = 'trainplex.2fa.partial'
_STEP_2FA_PENDING = '2fa_pending'


def issue_partial_token(user_id: int) -> str:
    """Sign + return a partial-login token for ``user_id``.

    Caller MUST have already verified the user's password. The token does
    NOT prove who the request came from — it just carries the user_id
    forward to the 2FA-challenge endpoint without trusting a client
    cookie or query string.
    """
    if not user_id:
        raise ValueError('Cannot issue a partial-login token without a user_id.')
    payload = {'user_id': int(user_id), 'step': _STEP_2FA_PENDING}
    return signing.TimestampSigner(salt=_SALT).sign_object(payload)


def verify_partial_token(token: Optional[str]) -> Optional[int]:
    """Return the ``user_id`` carried by ``token`` if it's still valid.

    Returns ``None`` on any failure (bad signature, expired, wrong step,
    missing user_id). Never raises — the caller can treat ``None`` as
    "redirect to login".
    """
    if not token:
        return None
    try:
        payload = signing.TimestampSigner(salt=_SALT).unsign_object(
            token,
            max_age=_TOKEN_MAX_AGE_SECONDS,
        )
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get('step') != _STEP_2FA_PENDING:
        return None
    user_id = payload.get('user_id')
    if not isinstance(user_id, int) or user_id <= 0:
        return None
    return user_id


__all__ = [
    'issue_partial_token',
    'verify_partial_token',
]
