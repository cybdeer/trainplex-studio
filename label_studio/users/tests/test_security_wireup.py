"""TrainPlex Phase 1 Step 12 wire-in tests.

These tests verify that the existing rate-limit decorators + audit_logger
service (built in Step 12.x but not yet wired) are now actually applied
to the HTTP-facing views:

- ``users.views.user_login`` carries ``@ratelimit_login`` (5/15m/IP).
- A 6th POST to ``/user/login/`` inside the window returns 429 with a
  Hindi-friendly JSON body.
- Successful + failed login attempts append rows to ``users.AuditLog``.
- ``UserAPI.update`` writes an ``AuditLog`` row when an admin changes a
  user's role.
- ``UserAPI.destroy`` writes an ``AuditLog`` row when an admin hard-deletes
  a user.
- The DRF ``custom_exception_handler`` converts ``Ratelimited`` raised by
  any DRF view into a 429 JSON body with the Hindi message.

Marked ``@pytest.mark.security_wireup`` so the suite can be run in
isolation:

    docker exec -w /label-studio/label_studio trainplex-studio-dev \
        /label-studio/.venv/bin/python -m pytest \
        users/tests/test_security_wireup.py -v
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, RequestFactory
from django.urls import reverse
from django_ratelimit.exceptions import Ratelimited

from users.models import AuditLog

User = get_user_model()

pytestmark = pytest.mark.security_wireup

# Note: ``USE_ENFORCE_CSRF_CHECKS=0`` is already set globally in pytest.ini's
# ``env =`` block, so we don't need ``@override_settings`` here — and that
# decorator would in any case reject the plain pytest classes below
# (it requires a ``SimpleTestCase`` subclass).


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_ratelimit_cache():
    """django-ratelimit stores counters in Django's cache. Reset between tests
    so each case starts with a clean budget.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def login_url():
    return reverse('user-login')


@pytest.fixture
def login_user(db):
    """A user we can POST valid credentials for."""
    user = User.objects.create_user(
        email='loginuser@trainplex.test',
        username='loginuser',
        password='correct-pass-123',
        role='trainer',
    )
    # users.functions.login looks up Organization.find_by_user — make sure
    # the user is in an org so the redirect path in the view doesn't blow up.
    from organizations.models import Organization

    Organization.create_organization(created_by=user, title='Sec wire-in org')
    user.refresh_from_db()
    return user


# ---------------------------------------------------------------------------
# 1. Login view — rate-limit decorator + Hindi 429 body
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLoginRateLimit:
    """``@ratelimit_login`` on ``users.views.user_login`` — 5 attempts per
    15 min per IP, 6th gets a JSON 429."""

    def test_sixth_login_attempt_returns_429(self, login_url):
        client = Client(REMOTE_ADDR='10.99.0.1')

        # Burn the budget with 5 bad attempts (form fails -> 200 + form error).
        for i in range(5):
            resp = client.post(login_url, {'email': f'nobody{i}@trainplex.test', 'password': 'wrong'})
            assert resp.status_code in (200, 302), f'attempt {i + 1} got {resp.status_code}'

        # 6th attempt should be rate-limited.
        resp = client.post(login_url, {'email': 'nobody@trainplex.test', 'password': 'wrong'})
        assert resp.status_code == 429, f'expected 429, got {resp.status_code}'

    def test_rate_limit_body_has_hindi_message(self, login_url):
        client = Client(REMOTE_ADDR='10.99.0.2')

        for _ in range(5):
            client.post(login_url, {'email': 'x@trainplex.test', 'password': 'wrong'})

        resp = client.post(login_url, {'email': 'x@trainplex.test', 'password': 'wrong'})
        assert resp.status_code == 429
        body = resp.json()
        assert body.get('error') == 'rate_limited'
        # Hindi-friendly message ships in 'message' (also mirrored to 'detail').
        assert 'Bahut sare requests' in body.get('message', '')
        assert body.get('retry_after_seconds') == 60


# ---------------------------------------------------------------------------
# 2. Audit log for login attempts
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLoginAuditLog:
    def test_successful_login_creates_audit_row(self, login_url, login_user):
        client = Client(REMOTE_ADDR='10.99.0.10', HTTP_USER_AGENT='pytest-ua')
        resp = client.post(login_url, {'email': login_user.email, 'password': 'correct-pass-123'})

        # On success the view redirects to next_page (302).
        assert resp.status_code in (200, 302)

        entry = AuditLog.objects.filter(
            user=login_user,
            action=AuditLog.ACTION_LOGIN_SUCCESS,
        ).first()
        assert entry is not None, 'No AuditLog row for successful login'
        assert entry.success is True
        assert entry.ip_address == '10.99.0.10'
        assert entry.user_agent == 'pytest-ua'

    def test_failed_login_creates_audit_row_with_success_false(self, login_url, login_user):
        client = Client(REMOTE_ADDR='10.99.0.11', HTTP_USER_AGENT='pytest-ua')
        resp = client.post(login_url, {'email': login_user.email, 'password': 'WRONG-PASS'})
        assert resp.status_code in (200, 302)  # form invalid -> 200 with errors

        entry = AuditLog.objects.filter(action=AuditLog.ACTION_LOGIN_FAIL).first()
        assert entry is not None, 'No AuditLog row for failed login'
        assert entry.success is False
        # ``user`` is NULL on failures — we don't trust the attacker-supplied email.
        assert entry.user_id is None
        assert entry.ip_address == '10.99.0.11'


# ---------------------------------------------------------------------------
# 3. Permission change audit
# ---------------------------------------------------------------------------
#
# OSS LS upstream does NOT expose an HTTP endpoint that allows changing a
# user's role:
#   - ``UserAPI.http_method_names`` excludes ``put`` entirely.
#   - ``UserSerializerUpdate`` (used by PATCH) marks ``role`` as
#     ``read_only_fields``.
# Role changes therefore happen via Django admin (or a future TrainPlex
# admin-only endpoint). To exercise the wire-in we drive
# ``UserAPI.update`` directly — exactly the path that lights up when a
# downstream re-enables PUT or wires a custom admin endpoint.


@pytest.mark.django_db
class TestPermissionChangeAudit:
    """Direct-method tests for the audit hook in ``UserAPI.update``.

    We can't go through the URL router because ``UserAPI.http_method_names``
    blocks PUT — but the hook MUST already be in place so it fires the
    instant role-change is re-enabled.
    """

    def _make_view(self, admin_user, target, payload):
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory, force_authenticate

        from users.api import UserAPI

        factory = APIRequestFactory()
        raw_req = factory.put(
            f'/api/users/{target.pk}/', data=payload, format='json', REMOTE_ADDR='10.99.0.20'
        )
        force_authenticate(raw_req, user=admin_user)
        # Wrap as DRF Request so .data + auth work the same way the router
        # would have wrapped it.
        drf_req = Request(raw_req, parsers=[__import__('rest_framework.parsers', fromlist=['JSONParser']).JSONParser()])
        drf_req.user = admin_user

        view = UserAPI()
        # Minimal viewset boilerplate so .update() can run without going
        # through dispatch() (which would re-trigger http_method_names).
        view.request = drf_req
        view.format_kwarg = None
        view.kwargs = {'pk': target.pk}
        view.action = 'update'
        return view, drf_req

    def test_role_change_in_update_creates_audit_row(self, admin_user, organization, monkeypatch):
        """Simulate the future admin-only role-change path.

        Today both ``UserSerializerUpdate`` (used by PATCH/PUT) and
        ``http_method_names`` block role writes. We monkey-patch the
        serializer to allow the write so we can verify the audit hook fires
        when an admin DOES change a role. This same hook will keep firing
        when a downstream/future LS version re-enables the write.
        """
        from users.api import UserAPI
        from users.serializers import UserSerializer

        target = User.objects.create_user(
            email='roletarget@trainplex.test',
            username='roletarget',
            password='pw',
            role='trainer',
        )
        target.active_organization = organization
        target.save(update_fields=['active_organization'])
        organization.add_user(target)

        old_count = AuditLog.objects.filter(action=AuditLog.ACTION_PERMISSION_CHANGE).count()

        view, req = self._make_view(
            admin_user,
            target,
            {'email': target.email, 'username': target.username, 'role': 'reviewer'},
        )
        # Force PUT path to use the role-writable serializer.
        monkeypatch.setattr(view, 'get_serializer_class', lambda: UserSerializer)
        view.update(req, pk=target.pk)

        target.refresh_from_db()
        assert target.role == 'reviewer', f'Role did not persist: actual={target.role!r}'

        new_count = AuditLog.objects.filter(action=AuditLog.ACTION_PERMISSION_CHANGE).count()
        assert new_count == old_count + 1, 'Role changed but no AuditLog row was written'
        entry = AuditLog.objects.filter(action=AuditLog.ACTION_PERMISSION_CHANGE).latest('created_at')
        assert entry.metadata['old_role'] == 'trainer'
        assert entry.metadata['new_role'] == 'reviewer'
        assert entry.target_id == str(target.id)
        assert entry.user_id == admin_user.id

    def test_no_audit_row_when_role_unchanged(self, admin_user, organization):
        """Invariant: only an actual role change writes the audit row."""
        target = User.objects.create_user(
            email='same-role@trainplex.test',
            username='sameroleuser',
            password='pw',
            role='trainer',
        )
        target.active_organization = organization
        target.save(update_fields=['active_organization'])
        organization.add_user(target)

        old_count = AuditLog.objects.filter(action=AuditLog.ACTION_PERMISSION_CHANGE).count()

        view, req = self._make_view(
            admin_user,
            target,
            {'email': target.email, 'username': target.username, 'role': 'trainer'},
        )
        view.update(req, pk=target.pk)

        new_count = AuditLog.objects.filter(action=AuditLog.ACTION_PERMISSION_CHANGE).count()
        assert new_count == old_count, 'AuditLog row was written without a real role change'


# ---------------------------------------------------------------------------
# 4. Delete audit
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDeleteAudit:
    def test_user_destroy_creates_audit_row(self, authenticated_client, organization):
        target = User.objects.create_user(
            email='deltarget@trainplex.test',
            username='deltarget',
            password='pw',
            role='trainer',
        )
        target.active_organization = organization
        target.save(update_fields=['active_organization'])
        organization.add_user(target)

        old_count = AuditLog.objects.filter(action=AuditLog.ACTION_DELETE).count()
        resp = authenticated_client.delete(f'/api/users/{target.id}/')
        assert resp.status_code in (204, 200, 404)  # 404 acceptable if org isolation hides it

        if not User.objects.filter(id=target.id).exists():
            new_count = AuditLog.objects.filter(action=AuditLog.ACTION_DELETE).count()
            assert new_count == old_count + 1, 'User was deleted but no AuditLog row was written'
            entry = AuditLog.objects.filter(
                action=AuditLog.ACTION_DELETE,
                target_type='User',
            ).latest('created_at')
            assert entry.target_id == str(target.id)
            assert entry.metadata.get('target_email') == 'deltarget@trainplex.test'


# ---------------------------------------------------------------------------
# 5. DRF exception handler converts Ratelimited to 429 JSON
# ---------------------------------------------------------------------------


class TestDRFRatelimitedHandler:
    """The shared DRF ``custom_exception_handler`` should turn any
    ``Ratelimited`` raised by a DRF view into a 429 JSON body with the
    Hindi message — independent of which decorator triggered it."""

    def test_handler_returns_429_with_hindi_body(self):
        from core.utils.common import custom_exception_handler

        rf = RequestFactory()
        fake_request = rf.post('/api/something')

        exc = Ratelimited()
        resp = custom_exception_handler(exc, {'request': fake_request})

        assert resp is not None
        assert resp.status_code == 429
        data = resp.data
        assert data['error'] == 'rate_limited'
        assert 'Bahut sare requests' in data['message']
        assert data['retry_after_seconds'] == 60
        assert resp['Retry-After'] == '60'


# ---------------------------------------------------------------------------
# 6. ratelimit_view fallback (global RATELIMIT_VIEW)
# ---------------------------------------------------------------------------


class TestRatelimitViewFallback:
    """Confirm ``users.views.ratelimit_view`` returns the same Hindi 429
    body that DRF returns. This is what ``RatelimitMiddleware`` hands back
    to plain Django views (e.g. our HTML login page)."""

    def test_returns_429_with_hindi_message(self):
        from users.views import ratelimit_view

        rf = RequestFactory()
        resp = ratelimit_view(rf.post('/anything'), Ratelimited())

        assert resp.status_code == 429
        import json

        body = json.loads(resp.content)
        assert body['error'] == 'rate_limited'
        assert 'Bahut sare requests' in body['message']
        assert body['retry_after_seconds'] == 60
        assert resp['Retry-After'] == '60'
