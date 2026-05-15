"""Tests for the TrainPlex health endpoints — Week 8 Step 11.

Covers
------
``HealthShallowAPI`` (``GET /api/v1/health``):
- Anonymous caller gets 200.
- Response shape matches the documented contract.
- `X-TrainPlex-Health` header is set.
- DB ping success → `db=ok`, overall `status=ok`.
- Forced DB failure → `db=fail`, overall `status=down`.
- `version` reads `$TRAINPLEX_VERSION` env when set.
- Uptime is a non-negative integer.

``HealthDeepAPI`` (``GET /api/v1/health/deep``):
- Anonymous → 401.
- Trainer (authenticated, not admin) → 403.
- Admin → 200 with all deep keys.
- `components.db.latency_ms` is a float.
- Redis check skip path returns `redis=skip` when no `$REDIS_LOCATION`.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


# ---------------------------------------------------------------------------
# Shallow probe — public.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHealthShallow(TestCase):
    """``GET /api/v1/health`` — should answer anyone, fast."""

    URL = '/api/v1/health'

    def setUp(self):
        self.client = APIClient()

    def test_anonymous_gets_200(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)

    def test_response_shape_is_contract(self):
        resp = self.client.get(self.URL)
        body = resp.json()
        # Required keys.
        for k in ('status', 'db', 'version', 'uptime_sec', 'now'):
            self.assertIn(k, body, msg=f'missing key: {k}')
        # `status` is one of the documented values.
        self.assertIn(body['status'], ('ok', 'degraded', 'down'))
        # `db` is one of the documented values.
        self.assertIn(body['db'], ('ok', 'fail', 'skip'))

    def test_response_header_set(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp['X-TrainPlex-Health'], resp.json()['status'])

    def test_uptime_is_non_negative_int(self):
        resp = self.client.get(self.URL)
        uptime = resp.json()['uptime_sec']
        self.assertIsInstance(uptime, int)
        self.assertGreaterEqual(uptime, 0)

    def test_version_env_passthrough(self):
        with patch.dict(os.environ, {'TRAINPLEX_VERSION': '9.9.9-test'}):
            resp = self.client.get(self.URL)
            self.assertEqual(resp.json()['version'], '9.9.9-test')

    def test_db_failure_marks_down(self):
        """Force the inner DB check to fail; overall flips to `down`."""
        from core import views_health

        with patch.object(
            views_health,
            '_check_db',
            return_value={
                'status': 'fail',
                'latency_ms': 12.3,
                'error_class': 'OperationalError',
            },
        ):
            resp = self.client.get(self.URL)
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertEqual(body['db'], 'fail')
            self.assertEqual(body['status'], 'down')

    def test_no_founder_mobile_in_response(self):
        """Defence-in-depth: even on failure, response body must not leak
        the founder's personal mobile (memory rule)."""
        resp = self.client.get(self.URL)
        self.assertNotIn('8764001234', resp.content.decode('utf-8'))


# ---------------------------------------------------------------------------
# Deep probe — admin only.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHealthDeep(TestCase):
    URL = '/api/v1/health/deep'

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='health-admin@example.com',
            username='health-admin',
            password='pw',
            role='admin',
        )
        self.trainer = User.objects.create_user(
            email='health-trainer@example.com',
            username='health-trainer',
            password='pw',
            role='trainer',
        )

    def test_anonymous_gets_401(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 401)

    def test_trainer_gets_403(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 403)

    def test_admin_gets_200_with_deep_keys(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # Shallow keys still present.
        for k in ('status', 'db', 'version', 'uptime_sec', 'now'):
            self.assertIn(k, body)
        # Deep-only keys.
        for k in ('redis', 'components', 'hostname', 'pid'):
            self.assertIn(k, body)
        # components.db carries the latency_ms float.
        self.assertIn('latency_ms', body['components']['db'])
        self.assertIsInstance(body['components']['db']['latency_ms'], float)

    def test_redis_skip_when_not_configured(self):
        """No `$REDIS_LOCATION` → redis check returns `skip`, not `fail`."""
        from django.conf import settings

        original = getattr(settings, 'REDIS_LOCATION', '')
        settings.REDIS_LOCATION = ''
        try:
            self.client.force_authenticate(user=self.admin)
            resp = self.client.get(self.URL)
            body = resp.json()
            self.assertEqual(body['redis'], 'skip')
            # `skip` does not degrade overall status.
            self.assertIn(body['status'], ('ok', 'degraded'))
        finally:
            settings.REDIS_LOCATION = original


# ---------------------------------------------------------------------------
# Snapshot helper — direct (no HTTP).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHealthSnapshotHelper(TestCase):
    """``health_snapshot(deep=...)`` is called directly from `dr_drill.sh`
    via the django management command; we lock the shape here so the
    drill never breaks silently."""

    def test_shallow_keys(self):
        from core.views_health import health_snapshot

        snap = health_snapshot(deep=False)
        self.assertEqual(
            set(snap.keys()) & {'status', 'db', 'version', 'uptime_sec', 'now'},
            {'status', 'db', 'version', 'uptime_sec', 'now'},
        )
        # Shallow does not include `components`.
        self.assertNotIn('components', snap)

    def test_deep_includes_components(self):
        from core.views_health import health_snapshot

        snap = health_snapshot(deep=True)
        self.assertIn('components', snap)
        self.assertIn('db', snap['components'])
