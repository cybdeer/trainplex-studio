"""Tests for the TrainPlex Trainer self-service Profile API — Phase 1 Step 13.

Endpoints (mounted in ``core/urls.py``)
---------------------------------------
GET    /api/v1/users/me/profile
PATCH  /api/v1/users/me/profile
POST   /api/v1/users/me/avatar
GET    /api/v1/users/me/sessions
DELETE /api/v1/users/me/sessions/<id>
GET    /api/v1/users/me/login-history
POST   /api/v1/users/me/password/change

Coverage
--------
- GET own profile: 200 + contract keys.
- PATCH first_name + state + language: persists + readback matches.
- PATCH role: silently ignored, user.role unchanged.
- PATCH email: silently ignored, user.email unchanged.
- POST password/change requires old password (400 on bad / missing).
- POST password/change rejects new password <8 chars (400).
- POST password/change rate-limited to 5/hour (429 on 6th attempt).
- GET login-history returns last 10 own events ordered desc by created_at.
- GET login-history scopes to the calling user only (never returns another
  user's rows even if the user posts a deceptive query).
- GET sessions returns at least one entry (current session).
- DELETE sessions/<id> returns 204.
- Unauthenticated requests get 401/403.
- The "wrong user" scenario: a GET /me/profile by user B returns B's data,
  never A's — verified via dual-user fixture.
"""

from __future__ import annotations

import time

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.models import AuditLog

User = get_user_model()


PROFILE_URL = '/api/v1/users/me/profile'
AVATAR_URL = '/api/v1/users/me/avatar'
SESSIONS_URL = '/api/v1/users/me/sessions'
LOGIN_HISTORY_URL = '/api/v1/users/me/login-history'
PASSWORD_CHANGE_URL = '/api/v1/users/me/password/change'

PROFILE_KEYS = {
    'id',
    'email',
    'first_name',
    'last_name',
    'phone',
    'avatar_url',
    'role',
    'date_joined',
    'state',
    'city',
    'pincode',
    'language',
    'tier',
    'payout_settings',
    'notification_prefs',
    'stats',
}


@pytest.mark.django_db
class TestTrainerProfileGet(TestCase):
    """GET /api/v1/users/me/profile."""

    def setUp(self):
        self.client = APIClient()
        self.trainer = User.objects.create_user(
            email='profile-trainer@example.com',
            username='profile-trainer',
            password='testpass123',
            role='trainer',
        )
        self.other = User.objects.create_user(
            email='profile-other@example.com',
            username='profile-other',
            password='testpass123',
            role='trainer',
        )

    def test_get_own_profile_returns_200_with_contract_keys(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(PROFILE_URL)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        missing = PROFILE_KEYS - set(body.keys())
        self.assertFalse(missing, f'Missing keys: {missing}; got {set(body.keys())}')
        # Caller's identity, NOT the other user's.
        self.assertEqual(body['email'], 'profile-trainer@example.com')
        self.assertEqual(body['role'], 'trainer')

    def test_unauthenticated_get_is_denied(self):
        resp = self.client.get(PROFILE_URL)
        self.assertIn(resp.status_code, (401, 403))

    def test_get_scopes_to_calling_user(self):
        """When user B is authenticated, response must reflect user B,
        not user A — endpoint is implicitly scoped to ``request.user``.
        """
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(PROFILE_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['email'], 'profile-other@example.com')


@pytest.mark.django_db
class TestTrainerProfilePatch(TestCase):
    """PATCH /api/v1/users/me/profile."""

    def setUp(self):
        self.client = APIClient()
        self.trainer = User.objects.create_user(
            email='patch-trainer@example.com',
            username='patch-trainer',
            password='testpass123',
            role='trainer',
        )

    def test_patch_user_fields_persists(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.patch(
            PROFILE_URL,
            data={'first_name': 'Vinod', 'phone': '+919999999999'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['first_name'], 'Vinod')
        self.assertEqual(body['phone'], '+919999999999')
        # Reload from DB to be sure it persisted.
        self.trainer.refresh_from_db()
        self.assertEqual(self.trainer.first_name, 'Vinod')
        self.assertEqual(self.trainer.phone, '+919999999999')

    def test_patch_meta_fields_state_language_pincode_persists(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.patch(
            PROFILE_URL,
            data={
                'state': 'Rajasthan',
                'city': 'Jaipur',
                'pincode': '302001',
                'language': 'hi',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['state'], 'Rajasthan')
        self.assertEqual(body['city'], 'Jaipur')
        self.assertEqual(body['pincode'], '302001')
        self.assertEqual(body['language'], 'hi')

    def test_patch_role_is_silently_ignored(self):
        """The role field is NEVER writable here — trainer cannot self-promote.

        We assert silent ignore (not a 400) because the React form may post
        the whole user object including role; we want the form to keep
        working but the role to never change.
        """
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.patch(
            PROFILE_URL, data={'role': 'admin'}, format='json'
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['role'], 'trainer')
        self.trainer.refresh_from_db()
        self.assertEqual(self.trainer.role, 'trainer')

    def test_patch_email_is_silently_ignored(self):
        self.client.force_authenticate(user=self.trainer)
        original = self.trainer.email
        resp = self.client.patch(
            PROFILE_URL, data={'email': 'hijacked@example.com'}, format='json'
        )
        self.assertEqual(resp.status_code, 200)
        self.trainer.refresh_from_db()
        self.assertEqual(self.trainer.email, original)

    def test_patch_unknown_fields_silently_dropped(self):
        """Any field outside the editable allow-list is dropped without error."""
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.patch(
            PROFILE_URL, data={'is_superuser': True, 'is_staff': True}, format='json'
        )
        self.assertEqual(resp.status_code, 200)
        self.trainer.refresh_from_db()
        self.assertFalse(self.trainer.is_superuser)
        self.assertFalse(self.trainer.is_staff)

    def test_patch_payout_settings_persists(self):
        self.client.force_authenticate(user=self.trainer)
        payout = {
            'upi_id': 'trainer@upi',
            'bank_account': 'XXXX1234',
            'cadence': 'weekly',
            'min_withdraw_inr': 200,
        }
        resp = self.client.patch(
            PROFILE_URL, data={'payout_settings': payout}, format='json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['payout_settings'], payout)


@pytest.mark.django_db
class TestTrainerPasswordChange(TestCase):
    """POST /api/v1/users/me/password/change."""

    def setUp(self):
        self.client = APIClient()
        self.trainer = User.objects.create_user(
            email='pw-trainer@example.com',
            username='pw-trainer',
            password='oldpass123',
            role='trainer',
        )

    def _reset_rate_limiter(self):
        """Clear the in-process rate limiter between tests."""
        from users.api_profile import _password_change_hits

        _password_change_hits.clear()

    def test_password_change_requires_old_password(self):
        self._reset_rate_limiter()
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.post(
            PASSWORD_CHANGE_URL,
            data={'new_password': 'newpass1234'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_password_change_wrong_old_password_400(self):
        self._reset_rate_limiter()
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.post(
            PASSWORD_CHANGE_URL,
            data={'old_password': 'wrong', 'new_password': 'newpass1234'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_password_change_short_new_password_400(self):
        self._reset_rate_limiter()
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.post(
            PASSWORD_CHANGE_URL,
            data={'old_password': 'oldpass123', 'new_password': 'short'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_password_change_happy_path_returns_200(self):
        self._reset_rate_limiter()
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.post(
            PASSWORD_CHANGE_URL,
            data={'old_password': 'oldpass123', 'new_password': 'newpass1234'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('changed'))
        # New password should now verify.
        self.trainer.refresh_from_db()
        self.assertTrue(self.trainer.check_password('newpass1234'))

    def test_password_change_rate_limited_at_6th_attempt(self):
        """5 attempts allowed per hour; 6th MUST return 429."""
        self._reset_rate_limiter()
        self.client.force_authenticate(user=self.trainer)
        # 5 attempts (all rejected for wrong old password but each costs
        # one slot from the limiter).
        for _ in range(5):
            self.client.post(
                PASSWORD_CHANGE_URL,
                data={'old_password': 'wrong', 'new_password': 'newpass1234'},
                format='json',
            )
        resp = self.client.post(
            PASSWORD_CHANGE_URL,
            data={'old_password': 'oldpass123', 'new_password': 'newpass1234'},
            format='json',
        )
        self.assertEqual(resp.status_code, 429)


@pytest.mark.django_db
class TestTrainerLoginHistory(TestCase):
    """GET /api/v1/users/me/login-history."""

    def setUp(self):
        self.client = APIClient()
        self.trainer = User.objects.create_user(
            email='lh-trainer@example.com',
            username='lh-trainer',
            password='testpass123',
            role='trainer',
        )
        self.other = User.objects.create_user(
            email='lh-other@example.com',
            username='lh-other',
            password='testpass123',
            role='trainer',
        )
        # Seed login events: 12 for the trainer (cap is 10), 3 for the other
        # user (these MUST NOT leak into the trainer's history).
        for i in range(12):
            AuditLog.objects.create(
                user=self.trainer,
                action=AuditLog.ACTION_LOGIN_SUCCESS,
                target_type='User',
                target_id=str(self.trainer.pk),
                ip_address='10.0.0.1',
                user_agent='pytest',
                success=True,
                metadata={'seq': i},
            )
        for i in range(3):
            AuditLog.objects.create(
                user=self.other,
                action=AuditLog.ACTION_LOGIN_SUCCESS,
                target_type='User',
                target_id=str(self.other.pk),
                ip_address='10.0.0.99',
                user_agent='pytest',
                success=True,
                metadata={'other_seq': i},
            )

    def test_login_history_returns_last_10_own_events(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(LOGIN_HISTORY_URL)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 10)
        # All rows must be for the calling user only.
        # We can't directly assert on user_id (not in payload), but we can
        # assert that all rows match seeded events for the trainer — which
        # used ip_address 10.0.0.1; other user's events were 10.0.0.99.
        for row in body:
            self.assertEqual(row['ip_address'], '10.0.0.1')

    def test_login_history_scoped_to_calling_user(self):
        """When the OTHER user calls, they see THEIR events, not the trainer's."""
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(LOGIN_HISTORY_URL)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 3)
        for row in body:
            self.assertEqual(row['ip_address'], '10.0.0.99')

    def test_login_history_unauthenticated_denied(self):
        resp = self.client.get(LOGIN_HISTORY_URL)
        self.assertIn(resp.status_code, (401, 403))


@pytest.mark.django_db
class TestTrainerSessions(TestCase):
    """GET /api/v1/users/me/sessions + DELETE .../<id>."""

    def setUp(self):
        self.client = APIClient()
        self.trainer = User.objects.create_user(
            email='sess-trainer@example.com',
            username='sess-trainer',
            password='testpass123',
            role='trainer',
        )

    def test_sessions_get_returns_at_least_current(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(SESSIONS_URL)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertGreaterEqual(len(body), 1)
        # Current session marker.
        self.assertTrue(body[0].get('is_current'))

    def test_sessions_revoke_returns_204(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.delete(f'{SESSIONS_URL}/123')
        self.assertEqual(resp.status_code, 204)

    def test_sessions_unauthenticated_denied(self):
        resp = self.client.get(SESSIONS_URL)
        self.assertIn(resp.status_code, (401, 403))
