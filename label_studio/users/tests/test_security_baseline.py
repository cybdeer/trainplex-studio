"""Tests for Phase 1 Step 12 Security Baseline.

Covers:
- Rate-limit decorators reject 6th call inside the window and reset
  after the window passes (freezegun).
- ``SecurityHeadersMiddleware`` adds HSTS / X-Frame-Options / etc.
- ``AuditLog.log_login`` records a row with the correct fields.
- TOTP secret generation length, ``verify_token`` accept/reject behaviour.
- Backup-code hash + verify roundtrip (and one-time-use consumption).
- ``user_needs_2fa`` returns True for admin, False for trainer.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory
from django_ratelimit.exceptions import Ratelimited
from freezegun import freeze_time

from users.middleware.rate_limit import (
    API_RATE,
    LOGIN_RATE,
    OTP_RATE,
    PASSWORD_RESET_RATE,
    ratelimit_api,
    ratelimit_login,
    ratelimit_otp,
    ratelimit_password_reset,
)
from users.middleware.security_headers import SecurityHeadersMiddleware
from users.models import AuditLog, user_needs_2fa
from users.services import audit_logger, totp_handler

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_ratelimit_cache():
    """django-ratelimit stores counters in the Django cache; reset between tests
    so individual cases don't leak state into each other.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def rf():
    return RequestFactory()


def _ok_view(request):  # noqa: ARG001
    return HttpResponse('ok')


# ---------------------------------------------------------------------------
# Policy constants — guard against accidental rate changes
# ---------------------------------------------------------------------------


def test_policy_constants():
    """Policy strings stay locked to the values in the Step 12 brief."""
    assert LOGIN_RATE == '5/15m'
    assert API_RATE == '100/m'
    assert OTP_RATE == '3/15m'
    assert PASSWORD_RESET_RATE == '3/h'


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimitLogin:
    """5 attempts per 15 min per IP — 6th call must be rejected."""

    def test_sixth_request_is_blocked(self, rf):
        view = ratelimit_login(_ok_view)

        # The first 5 requests succeed.
        for _ in range(5):
            req = rf.post('/login', REMOTE_ADDR='10.0.0.1')
            resp = view(req)
            assert resp.status_code == 200

        # The 6th must raise Ratelimited (block=True).
        req = rf.post('/login', REMOTE_ADDR='10.0.0.1')
        with pytest.raises(Ratelimited):
            view(req)

    def test_window_resets_after_time_passes(self, rf):
        """After 15 min the counter rolls over and the user can try again."""
        view = ratelimit_login(_ok_view)

        with freeze_time('2026-01-01 00:00:00') as frozen:
            # Burn the budget.
            for _ in range(5):
                view(rf.post('/login', REMOTE_ADDR='10.0.0.2'))
            with pytest.raises(Ratelimited):
                view(rf.post('/login', REMOTE_ADDR='10.0.0.2'))

            # Move past the 15-minute window — the bucket resets.
            frozen.tick(delta=__import__('datetime').timedelta(minutes=16))
            resp = view(rf.post('/login', REMOTE_ADDR='10.0.0.2'))
            assert resp.status_code == 200

    def test_different_ip_has_independent_budget(self, rf):
        """Per-IP keying — exhausting one IP doesn't lock out a different one."""
        view = ratelimit_login(_ok_view)

        for _ in range(5):
            view(rf.post('/login', REMOTE_ADDR='10.0.0.3'))
        with pytest.raises(Ratelimited):
            view(rf.post('/login', REMOTE_ADDR='10.0.0.3'))

        # Different IP → fresh bucket.
        resp = view(rf.post('/login', REMOTE_ADDR='10.0.0.4'))
        assert resp.status_code == 200


class TestRateLimitOTP:
    """3 requests per 15 min per mobile."""

    def test_fourth_otp_request_blocked(self, rf):
        view = ratelimit_otp(_ok_view)

        for _ in range(3):
            resp = view(rf.post('/otp', {'mobile': '+919876543210'}))
            assert resp.status_code == 200

        with pytest.raises(Ratelimited):
            view(rf.post('/otp', {'mobile': '+919876543210'}))


class TestRateLimitPasswordReset:
    """3 requests per hour per email."""

    def test_fourth_reset_request_blocked(self, rf):
        view = ratelimit_password_reset(_ok_view)

        for _ in range(3):
            resp = view(rf.post('/forgot', {'email': 'user@example.com'}))
            assert resp.status_code == 200

        with pytest.raises(Ratelimited):
            view(rf.post('/forgot', {'email': 'user@example.com'}))


class TestRateLimitAPI:
    """100 requests per minute per IP — sanity check that the decorator is wired,
    not a full burn-down (would be slow + flaky)."""

    def test_decorator_is_callable_and_under_limit_passes(self, rf):
        view = ratelimit_api(_ok_view)
        resp = view(rf.get('/api/ping', REMOTE_ADDR='10.0.0.99'))
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------


class TestSecurityHeadersMiddleware:
    def test_all_baseline_headers_set(self, rf):
        mw = SecurityHeadersMiddleware(get_response=lambda r: HttpResponse('ok'))
        resp = mw(rf.get('/'))

        assert resp['Strict-Transport-Security'] == 'max-age=31536000; includeSubDomains'
        assert resp['X-Content-Type-Options'] == 'nosniff'
        assert resp['X-Frame-Options'] == 'DENY'
        assert resp['Referrer-Policy'] == 'strict-origin-when-cross-origin'
        assert resp['Permissions-Policy'] == 'geolocation=(), microphone=(), camera=()'

    def test_does_not_clobber_existing_header(self, rf):
        """If a downstream view/middleware has already set a tighter HSTS,
        we preserve it (setdefault semantics)."""

        def _custom_hsts(request):  # noqa: ARG001
            r = HttpResponse('ok')
            r['Strict-Transport-Security'] = 'max-age=63072000; preload'
            return r

        mw = SecurityHeadersMiddleware(get_response=_custom_hsts)
        resp = mw(rf.get('/'))

        assert resp['Strict-Transport-Security'] == 'max-age=63072000; preload'


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuditLogger:
    def test_log_login_success_creates_row(self, admin_user):
        entry = audit_logger.log_login(admin_user, ip='10.0.0.5', ua='pytest-ua', success=True)

        assert entry is not None
        assert entry.user_id == admin_user.id
        assert entry.action == AuditLog.ACTION_LOGIN_SUCCESS
        assert entry.target_type == 'User'
        assert entry.target_id == str(admin_user.id)
        assert entry.ip_address == '10.0.0.5'
        assert entry.user_agent == 'pytest-ua'
        assert entry.success is True

    def test_log_login_failure_with_no_user(self):
        entry = audit_logger.log_login(user=None, ip='10.0.0.6', ua='pytest-ua', success=False)

        assert entry is not None
        assert entry.user is None
        assert entry.action == AuditLog.ACTION_LOGIN_FAIL
        assert entry.success is False

    def test_log_permission_change(self, admin_user, trainer_user):
        entry = audit_logger.log_permission_change(
            actor=admin_user,
            target=trainer_user,
            old_role='trainer',
            new_role='reviewer',
            ip='10.0.0.7',
        )

        assert entry.action == AuditLog.ACTION_PERMISSION_CHANGE
        assert entry.metadata['old_role'] == 'trainer'
        assert entry.metadata['new_role'] == 'reviewer'
        assert entry.metadata['target_email'] == trainer_user.email
        assert entry.target_id == str(trainer_user.id)

    def test_log_delete(self, admin_user):
        entry = audit_logger.log_delete(
            actor=admin_user,
            target_type='Project',
            target_id=42,
            ip='10.0.0.8',
            metadata={'project_title': 'demo'},
        )

        assert entry.action == AuditLog.ACTION_DELETE
        assert entry.target_type == 'Project'
        assert entry.target_id == '42'
        assert entry.metadata['project_title'] == 'demo'

    def test_log_admin_action(self, admin_user):
        entry = audit_logger.log_admin_action(
            actor=admin_user,
            action_name='export_data',
            metadata={'format': 'csv'},
            ip='10.0.0.9',
        )

        assert entry.action == AuditLog.ACTION_ADMIN_ACTION
        assert entry.metadata['action_name'] == 'export_data'
        assert entry.metadata['format'] == 'csv'


# ---------------------------------------------------------------------------
# TOTP handler
# ---------------------------------------------------------------------------


class TestTOTPHandler:
    def test_generate_secret_length_and_base32(self):
        secret = totp_handler.generate_secret()
        # pyotp's random_base32 returns 32 base32 chars by default.
        assert len(secret) == 32
        assert set(secret).issubset(set('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'))

    def test_two_secrets_are_distinct(self):
        """Sanity: two consecutive secrets should not collide."""
        assert totp_handler.generate_secret() != totp_handler.generate_secret()

    def test_verify_token_accepts_current_code(self):
        import pyotp

        secret = totp_handler.generate_secret()
        valid_token = pyotp.TOTP(secret).now()
        assert totp_handler.verify_token(secret, valid_token) is True

    def test_verify_token_rejects_bad_code(self):
        secret = totp_handler.generate_secret()
        assert totp_handler.verify_token(secret, '000000') is False

    def test_verify_token_rejects_non_numeric(self):
        secret = totp_handler.generate_secret()
        assert totp_handler.verify_token(secret, 'abcdef') is False
        assert totp_handler.verify_token(secret, '12345') is False  # too short
        assert totp_handler.verify_token(secret, '') is False

    @pytest.mark.django_db
    def test_get_provisioning_uri_includes_email_and_issuer(self, admin_user):
        secret = totp_handler.generate_secret()
        uri = totp_handler.get_provisioning_uri(admin_user, secret)
        assert uri.startswith('otpauth://totp/')
        assert 'TrainPlex' in uri
        # Account name is the user's email, URL-encoded by pyotp.
        assert admin_user.email.replace('@', '%40') in uri or admin_user.email in uri

    def test_get_provisioning_uri_rejects_empty_secret(self, admin_user_stub=None):
        class _Stub:
            email = 'a@b.test'
            username = 'a'

        with pytest.raises(ValueError):
            totp_handler.get_provisioning_uri(_Stub(), '')


class TestBackupCodes:
    def test_generate_returns_ten_unique_codes(self):
        codes = totp_handler.generate_backup_codes()
        assert len(codes) == 10
        assert len(set(codes)) == 10  # no duplicates
        # 4 bytes -> 8 hex chars
        for c in codes:
            assert len(c) == 8
            int(c, 16)  # raises if not hex

    def test_hash_is_deterministic(self):
        h1 = totp_handler.hash_backup_code('abcd1234')
        h2 = totp_handler.hash_backup_code('abcd1234')
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    @pytest.mark.django_db
    def test_verify_backup_code_roundtrip_and_consumes(self, admin_user):
        codes = totp_handler.generate_backup_codes()
        admin_user.backup_codes = [totp_handler.hash_backup_code(c) for c in codes]
        admin_user.save(update_fields=['backup_codes'])

        # First use succeeds...
        assert totp_handler.verify_backup_code(admin_user, codes[0]) is True
        admin_user.refresh_from_db()
        assert len(admin_user.backup_codes) == 9

        # ...and the same code can't be reused.
        assert totp_handler.verify_backup_code(admin_user, codes[0]) is False

        # A wrong code never matches.
        assert totp_handler.verify_backup_code(admin_user, 'deadbeef') is False


# ---------------------------------------------------------------------------
# user_needs_2fa role helper
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUserNeeds2FA:
    def test_admin_requires_2fa(self, admin_user):
        assert user_needs_2fa(admin_user) is True

    def test_trainer_does_not_require_2fa(self, trainer_user):
        assert user_needs_2fa(trainer_user) is False

    def test_reviewer_does_not_require_2fa(self, reviewer_user):
        assert user_needs_2fa(reviewer_user) is False

    def test_qa_lead_does_not_require_2fa(self, qa_lead_user):
        assert user_needs_2fa(qa_lead_user) is False

    def test_none_user_is_safe(self):
        assert user_needs_2fa(None) is False
