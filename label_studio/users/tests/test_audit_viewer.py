"""Tests for the TrainPlex admin audit-log viewer endpoint.

Phase 1 Step 4.2-4 — backend filter API for the React `<AuditLogPage />`.

Covers:
- Admin GET returns 200 + paginated rows + shape contract.
- Trainer (and unauthenticated) gets 403.
- ``action`` filter narrows to matching rows only.
- ``success=false`` filter returns failures only.
- Date-range filter (``start_date`` + ``end_date``) excludes out-of-window rows.
- Combinations that match nothing return an empty ``results`` list — no crash.
- ``page_size`` is hard-capped at 200 even if the client requests more.
- Pagination metadata (``page``, ``total``, ``total_pages``) is consistent.

Notes
-----
- We seed rows directly with ``AuditLog.objects.create`` so the test data is
  deterministic and doesn't depend on the login/role-change/delete hooks
  themselves working — those have their own test suites.
- ``created_at`` is set via ``filter().update()`` because the field has
  ``auto_now_add=True`` and won't accept an override on ``create``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from users.models import AuditLog

User = get_user_model()


@pytest.mark.django_db
class TestAdminAuditLogViewer(TestCase):
    """Endpoint: GET /api/v1/admin/audit/log."""

    URL = '/api/v1/admin/audit/log'

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='audit-admin@example.com',
            username='audit-admin',
            password='testpass123',
            role='admin',
        )
        self.trainer = User.objects.create_user(
            email='audit-trainer@example.com',
            username='audit-trainer',
            password='testpass123',
            role='trainer',
        )

    # -------- helpers --------

    def _make_row(
        self,
        action: str,
        *,
        user=None,
        success: bool = True,
        target_type: str = 'User',
        target_id: str = '',
        ip: str = '10.0.0.1',
        ua: str = 'pytest-agent',
        metadata: dict | None = None,
        when: datetime | None = None,
    ) -> AuditLog:
        row = AuditLog.objects.create(
            user=user,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip,
            user_agent=ua,
            success=success,
            metadata=metadata or {},
        )
        if when is not None:
            # ``auto_now_add`` blocks direct assignment on create() — sidestep
            # it with a .update() so the test row carries a deterministic timestamp.
            AuditLog.objects.filter(pk=row.pk).update(created_at=when)
            row.refresh_from_db()
        return row

    # -------- access control --------

    def test_admin_gets_200(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # Response shape contract.
        self.assertIn('page', body)
        self.assertIn('page_size', body)
        self.assertIn('total', body)
        self.assertIn('total_pages', body)
        self.assertIn('results', body)
        self.assertIsInstance(body['results'], list)

    def test_trainer_gets_403(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_rejected(self):
        resp = self.client.get(self.URL)
        # DRF returns 401 OR 403 for unauthenticated depending on auth class set.
        self.assertIn(resp.status_code, (401, 403))

    # -------- result shape --------

    def test_returns_paginated_rows_newest_first(self):
        """Three rows in, three rows back, newest ``created_at`` first."""
        now = datetime.now(timezone.utc)
        a = self._make_row('login_success', user=self.admin, when=now - timedelta(minutes=2))
        b = self._make_row('login_fail', user=None, success=False, when=now - timedelta(minutes=1))
        c = self._make_row('delete', user=self.admin, when=now)

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL)
        body = resp.json()

        self.assertEqual(body['total'], 3)
        ids = [r['id'] for r in body['results']]
        # Newest first ordering: c (newest), b, a (oldest).
        self.assertEqual(ids, [c.id, b.id, a.id])

    def test_row_shape_has_required_fields(self):
        self._make_row('login_success', user=self.admin)
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        row = body['results'][0]
        required = {
            'id', 'action', 'actor', 'target_type', 'target_id',
            'ip_address', 'user_agent', 'success', 'metadata', 'created_at',
        }
        self.assertTrue(required.issubset(row.keys()), f'Missing keys: {required - row.keys()}')
        self.assertEqual(row['action'], 'login_success')
        # actor contains email + role (admin in our seed) when user is set.
        self.assertIsNotNone(row['actor'])
        self.assertEqual(row['actor']['email'], self.admin.email)
        self.assertEqual(row['actor']['role'], 'admin')

    def test_user_agent_is_truncated_at_80_chars(self):
        long_ua = 'X' * 250
        self._make_row('login_success', user=self.admin, ua=long_ua)
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        ua_displayed = body['results'][0]['user_agent']
        # 80 X's + an ellipsis to signal truncation.
        self.assertEqual(len(ua_displayed), 81)
        self.assertTrue(ua_displayed.endswith('…'))

    def test_actor_is_null_for_anon_login_fail(self):
        self._make_row('login_fail', user=None, success=False)
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        self.assertIsNone(body['results'][0]['actor'])

    # -------- filters --------

    def test_filter_by_action(self):
        self._make_row('login_success', user=self.admin)
        self._make_row('login_fail', user=None, success=False)
        self._make_row('delete', user=self.admin, target_type='Project', target_id='42')

        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'action': 'login_fail'}).json()
        self.assertEqual(body['total'], 1)
        self.assertEqual(body['results'][0]['action'], 'login_fail')

    def test_filter_by_success_false(self):
        self._make_row('login_success', user=self.admin, success=True)
        self._make_row('login_fail', user=None, success=False)

        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'success': 'false'}).json()
        self.assertEqual(body['total'], 1)
        self.assertFalse(body['results'][0]['success'])

    def test_filter_by_target_type(self):
        self._make_row('login_success', user=self.admin, target_type='User')
        self._make_row('delete', user=self.admin, target_type='Project', target_id='42')

        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'target_type': 'Project'}).json()
        self.assertEqual(body['total'], 1)
        self.assertEqual(body['results'][0]['target_type'], 'Project')

    def test_filter_by_actor_email_substring(self):
        # Match by admin's email fragment; the unauthenticated row stays out.
        self._make_row('login_success', user=self.admin)
        self._make_row('login_fail', user=None, success=False)

        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'actor_email': 'audit-admin'}).json()
        self.assertEqual(body['total'], 1)
        self.assertEqual(body['results'][0]['actor']['email'], self.admin.email)

    def test_filter_by_date_range(self):
        """``start_date`` + ``end_date`` bound the ``created_at`` window inclusively."""
        now = datetime.now(timezone.utc)
        # Three rows: 5 days ago (out), 2 days ago (in), today (in).
        old = self._make_row('login_success', user=self.admin, when=now - timedelta(days=5))
        mid = self._make_row('login_success', user=self.admin, when=now - timedelta(days=2))
        new = self._make_row('login_success', user=self.admin, when=now)

        start = (now - timedelta(days=3)).date().isoformat()
        end = now.date().isoformat()

        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'start_date': start, 'end_date': end}).json()
        ids = {r['id'] for r in body['results']}
        self.assertEqual(ids, {mid.id, new.id})
        self.assertNotIn(old.id, ids)

    def test_empty_filter_combo_returns_no_crash(self):
        """Filters that match nothing must return ``results: []`` (no 500)."""
        self._make_row('login_success', user=self.admin)
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(
            self.URL,
            {'action': 'permission_change', 'success': 'false', 'target_type': 'DoesNotExist'},
        ).json()
        self.assertEqual(body['total'], 0)
        self.assertEqual(body['results'], [])
        self.assertEqual(body['total_pages'], 0)

    # -------- pagination --------

    def test_page_size_capped_at_200(self):
        """A client asking for 5000 rows still gets ``page_size=200``."""
        # No need to actually seed 5000 rows — the cap shows up in metadata
        # regardless of how many rows exist.
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'page_size': '5000'}).json()
        self.assertEqual(body['page_size'], 200)

    def test_page_size_default_is_50(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        self.assertEqual(body['page_size'], 50)
        self.assertEqual(body['page'], 1)

    def test_pagination_slices_results(self):
        """With 5 rows and page_size=2 we get 3 total_pages and 2 rows on page 1."""
        for _ in range(5):
            self._make_row('login_success', user=self.admin)

        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'page_size': '2', 'page': '1'}).json()
        self.assertEqual(body['total'], 5)
        self.assertEqual(body['total_pages'], 3)
        self.assertEqual(len(body['results']), 2)

        # Page 3 should have 1 row (last page).
        body3 = self.client.get(self.URL, {'page_size': '2', 'page': '3'}).json()
        self.assertEqual(len(body3['results']), 1)

    def test_invalid_page_falls_back_to_default(self):
        """Negative / non-numeric page values don't 500; they fall back."""
        self._make_row('login_success', user=self.admin)
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'page': '-2', 'page_size': 'abc'}).json()
        self.assertEqual(body['page'], 1)
        self.assertEqual(body['page_size'], 50)
