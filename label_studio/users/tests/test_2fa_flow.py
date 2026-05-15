"""Tests for the Phase 1 Step 12.4 2FA wire-in.

Covers:
- ``/api/v1/users/me/2fa/enroll/start``  — admin allowed, trainer 403
- ``/api/v1/users/me/2fa/enroll/confirm`` — valid token succeeds + persists,
                                            invalid token rejected
- Login flow — admin with 2FA on returns ``requires_2fa=true``,
               admin without 2FA gets the ``X-TrainPlex-2FA-Required`` header
- ``/user/login/2fa`` — valid token issues a session
                       — backup code issues a session + marks used
                       — same backup code twice → second 401
                       — invalid token → 401 + AuditLog (login_fail)
- ``/api/v1/users/me/2fa/disable`` — needs both password + token
"""

from __future__ import annotations

import json

import pyotp
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from users.models import AuditLog
from users.services import partial_login_token, totp_handler

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers + fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_ratelimit_cache():
    """Login views are wrapped in django-ratelimit; clear the cache between
    tests so one case's 5 attempts don't lock out the next.
    """
    cache.clear()
    yield
    cache.clear()


def _enroll_admin(admin_user) -> tuple[str, list[str]]:
    """Programmatically enroll ``admin_user`` in 2FA.

    Mirrors what the ``/enroll/confirm`` endpoint does — generates a
    secret, persists it, and seeds backup codes. Returns the secret +
    the plain backup codes so individual tests can use either.
    """
    secret = totp_handler.generate_secret()
    plain_codes = totp_handler.generate_backup_codes()
    admin_user.totp_secret = secret
    admin_user.totp_enabled = True
    admin_user.backup_codes = [totp_handler.hash_backup_code(c) for c in plain_codes]
    admin_user.save(update_fields=['totp_secret', 'totp_enabled', 'backup_codes'])
    return secret, plain_codes


# ---------------------------------------------------------------------------
# Enrollment — start
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEnrollStart:
    def test_admin_can_start_enrollment(self, admin_user):
        client = APIClient()
        client.force_authenticate(user=admin_user)
        resp = client.post('/api/v1/users/me/2fa/enroll/start')

        assert resp.status_code == 200
        body = resp.json()
        assert 'secret' in body
        assert 'provisioning_uri' in body
        assert body['provisioning_uri'].startswith('otpauth://totp/')
        # Importantly, totp_enabled is NOT flipped on start.
        admin_user.refresh_from_db()
        assert admin_user.totp_enabled is False

    def test_qa_lead_can_start_enrollment(self, qa_lead_user):
        client = APIClient()
        client.force_authenticate(user=qa_lead_user)
        resp = client.post('/api/v1/users/me/2fa/enroll/start')
        assert resp.status_code == 200

    def test_trainer_gets_403(self, trainer_user):
        client = APIClient()
        client.force_authenticate(user=trainer_user)
        resp = client.post('/api/v1/users/me/2fa/enroll/start')
        assert resp.status_code == 403

    def test_anonymous_gets_401_or_403(self):
        client = APIClient()
        resp = client.post('/api/v1/users/me/2fa/enroll/start')
        # IsAuthenticated → 401; if redirected to login, 403 also OK.
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Enrollment — confirm
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEnrollConfirm:
    def test_confirm_with_valid_token_persists(self, admin_user):
        client = APIClient()
        client.force_authenticate(user=admin_user)
        secret = totp_handler.generate_secret()
        valid_token = pyotp.TOTP(secret).now()

        resp = client.post(
            '/api/v1/users/me/2fa/enroll/confirm',
            {'secret': secret, 'token': valid_token},
            format='json',
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body['totp_enabled'] is True
        # 10 plain backup codes surfaced once.
        assert len(body['backup_codes']) == 10
        assert all(len(c) == 8 for c in body['backup_codes'])

        admin_user.refresh_from_db()
        assert admin_user.totp_enabled is True
        assert admin_user.totp_secret == secret
        assert len(admin_user.backup_codes) == 10
        # Stored copies are hashes, never plaintext.
        assert admin_user.backup_codes[0] != body['backup_codes'][0]

    def test_confirm_with_invalid_token_rejected(self, admin_user):
        client = APIClient()
        client.force_authenticate(user=admin_user)
        secret = totp_handler.generate_secret()

        resp = client.post(
            '/api/v1/users/me/2fa/enroll/confirm',
            {'secret': secret, 'token': '000000'},
            format='json',
        )

        assert resp.status_code == 400
        admin_user.refresh_from_db()
        assert admin_user.totp_enabled is False
        assert admin_user.totp_secret == ''

    def test_confirm_audit_event_written(self, admin_user):
        client = APIClient()
        client.force_authenticate(user=admin_user)
        secret = totp_handler.generate_secret()
        valid_token = pyotp.TOTP(secret).now()

        client.post(
            '/api/v1/users/me/2fa/enroll/confirm',
            {'secret': secret, 'token': valid_token},
            format='json',
        )

        events = AuditLog.objects.filter(
            user=admin_user,
            action=AuditLog.ACTION_ADMIN_ACTION,
        )
        assert events.exists()
        assert events.first().metadata.get('action_name') == '2fa_enrolled'


# ---------------------------------------------------------------------------
# Login flow gate
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_with_org(admin_user, organization):
    """Admin user already wired into an organization (membership row).

    The legacy ``user_login`` view calls ``Organization.find_by_user`` after
    password verification, which raises when no membership exists. The
    ``organization`` fixture in ``conftest.py`` creates the Organization and
    attaches the admin as the creating user, which gives the admin a
    membership row through the post-save signal in ``organizations.models``.
    """
    return admin_user


@pytest.fixture
def trainer_with_org(trainer_user, organization):
    """Trainer wired into the same Organization as ``admin_with_org``."""
    organization.add_user(trainer_user)
    trainer_user.active_organization = organization
    trainer_user.save(update_fields=['active_organization'])
    return trainer_user


@pytest.mark.django_db
class TestLoginGate:
    """``/user/login/`` returns ``requires_2fa`` for an admin with 2FA on."""

    def test_admin_with_2fa_returns_partial_token(self, admin_with_org):
        admin_with_org.set_password('correct-horse-battery')
        admin_with_org.save(update_fields=['password'])
        _enroll_admin(admin_with_org)

        client = Client()
        resp = client.post(
            reverse('user-login'),
            {
                'email': admin_with_org.email,
                'password': 'correct-horse-battery',
                'persist_session': True,
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body['requires_2fa'] is True
        assert 'partial_token' in body
        assert body['persist_session'] is True
        # Critical: NO Django session issued yet.
        assert '_auth_user_id' not in client.session

    def test_admin_without_2fa_gets_header(self, admin_with_org):
        admin_with_org.set_password('correct-horse-battery')
        admin_with_org.save(update_fields=['password'])
        # Don't enroll — admin still needs 2FA but hasn't set it up.

        client = Client()
        resp = client.post(
            reverse('user-login'),
            {
                'email': admin_with_org.email,
                'password': 'correct-horse-battery',
            },
        )

        # Redirect on success (302); session IS issued (soft mode).
        assert resp.status_code in (200, 302)
        assert resp.get('X-TrainPlex-2FA-Required') == 'true'

    def test_trainer_login_unchanged(self, trainer_with_org):
        """Trainers (don't need 2FA) bypass the 2FA gate entirely."""
        trainer_with_org.set_password('correct-horse-battery')
        trainer_with_org.save(update_fields=['password'])

        client = Client()
        resp = client.post(
            reverse('user-login'),
            {
                'email': trainer_with_org.email,
                'password': 'correct-horse-battery',
            },
        )

        # 302 redirect to projects/home, no 2FA header.
        assert resp.status_code in (200, 302)
        assert resp.get('X-TrainPlex-2FA-Required') is None


# ---------------------------------------------------------------------------
# 2FA challenge — /user/login/2fa
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLogin2FAVerify:
    def _start_2fa_login(self, admin_user, password='correct-horse-battery'):
        admin_user.set_password(password)
        admin_user.save(update_fields=['password'])
        secret, codes = _enroll_admin(admin_user)
        return secret, codes

    def test_valid_token_issues_session(self, admin_user):
        secret, _codes = self._start_2fa_login(admin_user)
        token = partial_login_token.issue_partial_token(admin_user.id)
        code = pyotp.TOTP(secret).now()

        client = Client()
        resp = client.post(
            reverse('user-login-2fa'),
            data=json.dumps({'partial_token': token, 'token': code}),
            content_type='application/json',
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True
        # Session is now authenticated.
        assert str(admin_user.id) == client.session.get('_auth_user_id')

    def test_valid_backup_code_issues_session_and_consumes(self, admin_user):
        _secret, codes = self._start_2fa_login(admin_user)
        token = partial_login_token.issue_partial_token(admin_user.id)

        client = Client()
        resp = client.post(
            reverse('user-login-2fa'),
            data=json.dumps({'partial_token': token, 'backup_code': codes[0]}),
            content_type='application/json',
        )

        assert resp.status_code == 200
        assert str(admin_user.id) == client.session.get('_auth_user_id')

        # The consumed code is gone.
        admin_user.refresh_from_db()
        assert len(admin_user.backup_codes) == 9

    def test_same_backup_code_twice_fails_second_time(self, admin_user):
        _secret, codes = self._start_2fa_login(admin_user)

        # First use succeeds.
        token1 = partial_login_token.issue_partial_token(admin_user.id)
        client1 = Client()
        resp1 = client1.post(
            reverse('user-login-2fa'),
            data=json.dumps({'partial_token': token1, 'backup_code': codes[0]}),
            content_type='application/json',
        )
        assert resp1.status_code == 200

        # Second use of the same code fails — code was atomically consumed.
        token2 = partial_login_token.issue_partial_token(admin_user.id)
        client2 = Client()
        resp2 = client2.post(
            reverse('user-login-2fa'),
            data=json.dumps({'partial_token': token2, 'backup_code': codes[0]}),
            content_type='application/json',
        )
        assert resp2.status_code == 401

    def test_invalid_token_returns_401_and_audits(self, admin_user):
        _secret, _codes = self._start_2fa_login(admin_user)
        token = partial_login_token.issue_partial_token(admin_user.id)

        # Snapshot the existing fail count so we can assert the delta.
        prev_fails = AuditLog.objects.filter(action=AuditLog.ACTION_LOGIN_FAIL).count()

        client = Client()
        resp = client.post(
            reverse('user-login-2fa'),
            data=json.dumps({'partial_token': token, 'token': '000000'}),
            content_type='application/json',
        )

        assert resp.status_code == 401
        fails_after = AuditLog.objects.filter(action=AuditLog.ACTION_LOGIN_FAIL).count()
        assert fails_after == prev_fails + 1

    def test_expired_or_garbage_partial_token_returns_401(self, admin_user):
        self._start_2fa_login(admin_user)

        client = Client()
        resp = client.post(
            reverse('user-login-2fa'),
            data=json.dumps({'partial_token': 'not-a-real-token', 'token': '000000'}),
            content_type='application/json',
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Disable
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDisable:
    def test_disable_requires_password_and_token(self, admin_user):
        admin_user.set_password('correct-horse-battery')
        admin_user.save(update_fields=['password'])
        secret, _codes = _enroll_admin(admin_user)
        valid_code = pyotp.TOTP(secret).now()

        client = APIClient()
        client.force_authenticate(user=admin_user)

        # Missing password → 400.
        resp = client.post(
            '/api/v1/users/me/2fa/disable',
            {'token': valid_code},
            format='json',
        )
        assert resp.status_code == 400

        # Missing token → 400.
        resp = client.post(
            '/api/v1/users/me/2fa/disable',
            {'password': 'correct-horse-battery'},
            format='json',
        )
        assert resp.status_code == 400

        # Wrong password → 400.
        resp = client.post(
            '/api/v1/users/me/2fa/disable',
            {'password': 'wrong-pass', 'token': valid_code},
            format='json',
        )
        assert resp.status_code == 400

        admin_user.refresh_from_db()
        assert admin_user.totp_enabled is True  # Still on.

        # Both correct → 200, 2FA off.
        resp = client.post(
            '/api/v1/users/me/2fa/disable',
            {'password': 'correct-horse-battery', 'token': pyotp.TOTP(secret).now()},
            format='json',
        )
        assert resp.status_code == 200
        admin_user.refresh_from_db()
        assert admin_user.totp_enabled is False
        assert admin_user.totp_secret == ''
        assert admin_user.backup_codes == []

    def test_disable_audit_event_written(self, admin_user):
        admin_user.set_password('correct-horse-battery')
        admin_user.save(update_fields=['password'])
        secret, _codes = _enroll_admin(admin_user)

        client = APIClient()
        client.force_authenticate(user=admin_user)
        client.post(
            '/api/v1/users/me/2fa/disable',
            {'password': 'correct-horse-battery', 'token': pyotp.TOTP(secret).now()},
            format='json',
        )

        events = AuditLog.objects.filter(
            user=admin_user,
            action=AuditLog.ACTION_ADMIN_ACTION,
            metadata__action_name='2fa_disabled',
        )
        assert events.exists()

    def test_disable_when_2fa_not_enabled_returns_400(self, admin_user):
        admin_user.set_password('correct-horse-battery')
        admin_user.save(update_fields=['password'])
        # Don't enroll.

        client = APIClient()
        client.force_authenticate(user=admin_user)
        resp = client.post(
            '/api/v1/users/me/2fa/disable',
            {'password': 'correct-horse-battery', 'token': '123456'},
            format='json',
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Partial-token signing helper (focused tests for the signing primitive)
# ---------------------------------------------------------------------------


class TestPartialLoginToken:
    def test_roundtrip(self):
        token = partial_login_token.issue_partial_token(42)
        assert partial_login_token.verify_partial_token(token) == 42

    def test_garbage_returns_none(self):
        assert partial_login_token.verify_partial_token('bogus') is None
        assert partial_login_token.verify_partial_token('') is None
        assert partial_login_token.verify_partial_token(None) is None

    def test_zero_user_id_rejected(self):
        with pytest.raises(ValueError):
            partial_login_token.issue_partial_token(0)
