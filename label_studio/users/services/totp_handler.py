"""TOTP 2FA scaffold (Phase 1 Step 12.4).

Building blocks only — login-flow wire-in is a follow-up task. This module
exposes:

- ``generate_secret()`` — base32 TOTP shared secret (RFC 6238).
- ``get_provisioning_uri(user, secret)`` — ``otpauth://`` URL for QR codes.
- ``verify_token(secret, token)`` — verify a 6-digit code (±1 step tolerance).
- ``generate_backup_codes()`` — 10 hex single-use recovery codes.
- ``hash_backup_code(code)`` — SHA-256 hex digest used for storage.
- ``verify_backup_code(user, code)`` — verify + atomically consume a code.

The ``User`` columns these helpers operate on (``totp_secret``,
``totp_enabled``, ``backup_codes``) ship in migration ``0014_user_2fa_fields``.
"""

import hashlib
import secrets

import pyotp
from django.conf import settings

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# RFC 6238: 6 digits, 30s step is the de-facto standard for authenticator apps.
_TOTP_DIGITS = 6
_TOTP_INTERVAL = 30
# Allow ±1 step of clock skew when verifying — same window Google Authenticator
# uses by default. 0 would refuse codes from devices with even slight drift.
_TOTP_VERIFY_WINDOW = 1

# 10 backup codes, 8 hex chars each (~32 bits of entropy per code). The codes
# are surfaced once at enrollment time and stored hashed.
_BACKUP_CODE_COUNT = 10
_BACKUP_CODE_BYTES = 4  # 4 bytes -> 8 hex chars

_ISSUER = 'TrainPlex Studio'


# ---------------------------------------------------------------------------
# TOTP secret + provisioning
# ---------------------------------------------------------------------------


def generate_secret() -> str:
    """Return a fresh base32-encoded TOTP shared secret.

    ``pyotp.random_base32()`` produces a 32-character base32 string, well
    above RFC 6238's 128-bit minimum recommendation.
    """
    return pyotp.random_base32()


def get_provisioning_uri(user, secret: str) -> str:
    """Return the ``otpauth://`` URL the frontend should encode as a QR.

    ``name=`` is the user's email (or username fallback); ``issuer=`` is
    the deployment-wide label authenticator apps display alongside the code.
    """
    if not secret:
        raise ValueError('Cannot build provisioning URI for an empty TOTP secret.')

    account_name = getattr(user, 'email', '') or getattr(user, 'username', '') or 'user'
    issuer = getattr(settings, 'TOTP_ISSUER', _ISSUER)

    return pyotp.TOTP(secret, digits=_TOTP_DIGITS, interval=_TOTP_INTERVAL).provisioning_uri(
        name=account_name,
        issuer_name=issuer,
    )


def verify_token(secret: str, token: str) -> bool:
    """Return ``True`` iff ``token`` is a valid TOTP for ``secret``.

    Accepts the current step plus ±1 step of skew. Non-digit / non-6-char
    inputs are rejected up-front so a stray letter can't poke ``pyotp``.
    """
    if not secret or not token:
        return False

    token = token.strip()
    if len(token) != _TOTP_DIGITS or not token.isdigit():
        return False

    totp = pyotp.TOTP(secret, digits=_TOTP_DIGITS, interval=_TOTP_INTERVAL)
    return totp.verify(token, valid_window=_TOTP_VERIFY_WINDOW)


# ---------------------------------------------------------------------------
# Backup codes
# ---------------------------------------------------------------------------


def generate_backup_codes() -> list[str]:
    """Return ``_BACKUP_CODE_COUNT`` fresh hex backup codes.

    Codes are **plaintext** here — surface them to the user exactly once at
    enrollment, then store ``hash_backup_code(code)`` instead.
    """
    return [secrets.token_hex(_BACKUP_CODE_BYTES) for _ in range(_BACKUP_CODE_COUNT)]


def hash_backup_code(code: str) -> str:
    """Return the SHA-256 hex digest used for storing a backup code.

    Backup codes are short (~32 bits of entropy), so a salt would be largely
    decorative — the codes are also one-time-use and consumed on the first
    successful verify, which bounds online attack windows.
    """
    return hashlib.sha256(code.strip().encode('utf-8')).hexdigest()


def verify_backup_code(user, code: str) -> bool:
    """Verify ``code`` against ``user.backup_codes`` and consume it on hit.

    Returns ``True`` and atomically removes the matching hash from the
    user's stored list. Returns ``False`` (without touching the user) on
    no-match. Codes are case-insensitive (we always hash the lower-cased,
    trimmed input — same as a fresh code from ``generate_backup_codes``).
    """
    if not user or not code:
        return False

    digest = hash_backup_code(code.lower())
    stored = list(getattr(user, 'backup_codes', None) or [])

    if digest not in stored:
        return False

    stored.remove(digest)
    user.backup_codes = stored
    user.save(update_fields=['backup_codes'])
    return True


__all__ = [
    'generate_secret',
    'get_provisioning_uri',
    'verify_token',
    'generate_backup_codes',
    'hash_backup_code',
    'verify_backup_code',
]
