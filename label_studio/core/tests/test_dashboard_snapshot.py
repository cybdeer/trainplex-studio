"""Tests for TrainPlex admin dashboard snapshot endpoint.

Phase 1 Step 4.2-1.

Covers:
- Admin role gets a 200 with the expected JSON shape.
- Trainer role is rejected with 403 (RBAC works end-to-end via the URL).
- Unauthenticated request is rejected (401).
- Mock data shape: 5 top trainers, all amounts are int (no paise).
- Top-level keys match the documented contract.

Real data wiring is Phase 2 (Step 8). This test file pins the contract so the
frontend can build against a stable shape until then.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestAdminDashboardSnapshot(TestCase):
    """Endpoint: GET /api/v1/admin/dashboard/snapshot."""

    URL = '/api/v1/admin/dashboard/snapshot'

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='dash-admin@example.com',
            username='dash-admin',
            password='testpass123',
            role='admin',
        )
        self.trainer = User.objects.create_user(
            email='dash-trainer@example.com',
            username='dash-trainer',
            password='testpass123',
            role='trainer',
        )

    # ---------------- access control ----------------

    def test_admin_gets_200(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)

    def test_trainer_gets_403(self):
        """Trainer is authenticated but lacks the admin role."""
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_gets_401_or_403(self):
        """Unauthenticated callers must be rejected.

        DRF returns 401 when an auth class supplies WWW-Authenticate and 403
        otherwise; both indicate "not allowed" — we accept either.
        """
        resp = self.client.get(self.URL)
        self.assertIn(resp.status_code, (401, 403))

    # ---------------- shape contract ----------------

    def test_response_has_expected_top_level_keys(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        self.assertEqual(
            set(body.keys()),
            {'as_of', 'today', 'top_trainers', 'alerts'},
        )

    def test_today_block_has_all_kpis(self):
        self.client.force_authenticate(user=self.admin)
        today = self.client.get(self.URL).json()['today']
        self.assertEqual(
            set(today.keys()),
            {
                'submissions_count',
                'submissions_delta_pct',
                'active_trainers',
                'pay_hold_total_inr',
                'pay_released_today_inr',
            },
        )
        # All amounts must be integers — UI does no paise math.
        for key, value in today.items():
            self.assertIsInstance(value, int, f'{key} must be int, got {type(value).__name__}')

    def test_mock_has_at_least_5_top_trainers(self):
        self.client.force_authenticate(user=self.admin)
        trainers = self.client.get(self.URL).json()['top_trainers']
        self.assertGreaterEqual(len(trainers), 5)

    def test_each_top_trainer_has_required_fields(self):
        self.client.force_authenticate(user=self.admin)
        trainers = self.client.get(self.URL).json()['top_trainers']
        required = {'id', 'name', 'state', 'tasks_today', 'earnings_today_inr'}
        for t in trainers:
            self.assertTrue(required.issubset(t.keys()), f'Missing keys in {t}')
            # tasks_today + earnings_today_inr must be integers
            self.assertIsInstance(t['tasks_today'], int)
            self.assertIsInstance(t['earnings_today_inr'], int)

    def test_alerts_block_has_three_counters(self):
        self.client.force_authenticate(user=self.admin)
        alerts = self.client.get(self.URL).json()['alerts']
        self.assertEqual(
            set(alerts.keys()),
            {'disputes_pending', 'quality_flags', 'stuck_payouts'},
        )
        for k, v in alerts.items():
            self.assertIsInstance(v, int, f'alert {k} must be int')

    def test_as_of_is_iso8601_zulu(self):
        """as_of must be ISO 8601 ending in Z so the UI can `new Date(...)` it."""
        self.client.force_authenticate(user=self.admin)
        as_of = self.client.get(self.URL).json()['as_of']
        self.assertTrue(as_of.endswith('Z'), f'as_of should end in Z, got {as_of}')
        self.assertIn('T', as_of)
