"""Tests for TrainPlex admin India geographic heatmap endpoint.

Phase 1 Step 4.2-6.

Covers:
- Admin role gets a 200 with 17 state entries.
- Trainer role is rejected with 403 (RBAC works end-to-end via the URL).
- Unauthenticated request is rejected (401/403).
- Each entry has the required keys (state_code, state_name, active_trainers,
  submissions_count, total_earnings_inr) and integer-only numerics (no paise).
- `period=today` / `period=week` / `period=month` all accepted (200).
- Unknown `period` values fall back to the default rather than 400 (so a stale
  frontend doesn't break the founder dashboard).

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
class TestAdminHeatmapStateActivity(TestCase):
    """Endpoint: GET /api/v1/admin/heatmap/state-activity."""

    URL = '/api/v1/admin/heatmap/state-activity'

    # The 17 Indian states from Step 4.2-6 spec — pinned so the frontend can
    # rely on every state showing up across queries. If this set ever changes
    # the test catches the contract break and the matching frontend tests
    # need to update too.
    EXPECTED_STATE_CODES = {
        'RJ', 'UP', 'MH', 'KA', 'GJ', 'PB', 'TN', 'MP', 'TG', 'WB',
        'BR', 'KL', 'JH', 'OR', 'AP', 'DL', 'AS',
    }

    REQUIRED_KEYS = {
        'state_code',
        'state_name',
        'active_trainers',
        'submissions_count',
        'total_earnings_inr',
    }

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='heatmap-admin@example.com',
            username='heatmap-admin',
            password='testpass123',
            role='admin',
        )
        self.trainer = User.objects.create_user(
            email='heatmap-trainer@example.com',
            username='heatmap-trainer',
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

    def test_unauthenticated_rejected(self):
        """DRF returns 401 when WWW-Authenticate is supplied, else 403."""
        resp = self.client.get(self.URL)
        self.assertIn(resp.status_code, (401, 403))

    # ---------------- shape contract ----------------

    def test_returns_17_entries(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 17)

    def test_all_expected_states_present(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        codes = {entry['state_code'] for entry in body}
        self.assertEqual(codes, self.EXPECTED_STATE_CODES)

    def test_each_entry_has_required_keys(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        for entry in body:
            self.assertTrue(
                self.REQUIRED_KEYS.issubset(entry.keys()),
                f'Missing keys in entry {entry}',
            )

    def test_numbers_are_integers_no_paise(self):
        """UI does no fractional / paise math — pin to int."""
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        for entry in body:
            for numeric_field in ('active_trainers', 'submissions_count', 'total_earnings_inr'):
                self.assertIsInstance(
                    entry[numeric_field],
                    int,
                    f'{entry["state_code"]}.{numeric_field} must be int, '
                    f'got {type(entry[numeric_field]).__name__}',
                )

    def test_state_names_non_empty_strings(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        for entry in body:
            self.assertIsInstance(entry['state_name'], str)
            self.assertTrue(entry['state_name'].strip(), 'state_name must be non-empty')
            self.assertIsInstance(entry['state_code'], str)
            self.assertTrue(entry['state_code'].strip(), 'state_code must be non-empty')

    # ---------------- period parameter ----------------

    def test_period_today_accepted(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL, {'period': 'today'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 17)

    def test_period_week_accepted(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL, {'period': 'week'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 17)

    def test_period_month_accepted(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL, {'period': 'month'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 17)

    def test_period_today_smaller_than_month(self):
        """Sanity: today's totals should be smaller than the month's totals."""
        self.client.force_authenticate(user=self.admin)
        today_body = self.client.get(self.URL, {'period': 'today'}).json()
        month_body = self.client.get(self.URL, {'period': 'month'}).json()
        today_total_subs = sum(e['submissions_count'] for e in today_body)
        month_total_subs = sum(e['submissions_count'] for e in month_body)
        self.assertLess(today_total_subs, month_total_subs)

    def test_unknown_period_falls_back_to_default(self):
        """Stale clients passing 'year' shouldn't break the dashboard — 200, not 400."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL, {'period': 'year'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 17)

    def test_default_period_is_month(self):
        """No period param should match `period=month`."""
        self.client.force_authenticate(user=self.admin)
        default_body = self.client.get(self.URL).json()
        month_body = self.client.get(self.URL, {'period': 'month'}).json()
        self.assertEqual(default_body, month_body)
