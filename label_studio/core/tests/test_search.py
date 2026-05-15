"""Tests for the TrainPlex admin Global Search (Cmd+K) endpoint.

Phase 1 Step 14.

Covers
------
- Admin role gets a 200 with the expected JSON shape (flat array).
- Trainer / reviewer / qa_lead all rejected with 403.
- Unauthenticated request rejected (401 or 403).
- Empty ``q`` returns ``[]`` — NOT 400 (palette opens with empty input).
- Whitespace-only ``q`` returns ``[]``.
- ``q=Geeta`` returns trainer Geeta (case-insensitive, substring).
- ``q=hindi`` returns mixed types (trainer + project at least).
- ``scope=trainers`` returns only trainer rows.
- ``scope=projects`` returns only project rows.
- ``scope=submissions`` returns only submission rows.
- ``scope=audit_logs`` returns only audit rows.
- ``scope=tasks`` returns only task rows.
- ``scope=all`` default returns mixed types when applicable.
- Unknown scope silently falls back to ``all``.
- Per-row contract: ``type``, ``id``, ``title``, ``subtitle``, ``url`` keys.
- ``type`` is always one of the 5 known strings.
- ``url`` always starts with ``/admin/``.
- Max-50 results cap honoured (mock dataset is small but the cap path
  is exercised by a broad-needle query).
- Internal ``_search`` field NOT leaked to the client.

Real DB wiring is Phase 2 (Step 8). This file pins the contract so the
frontend Cmd+K palette stays stable across the swap.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


_VALID_TYPES = {'trainer', 'project', 'submission', 'audit', 'task'}
_REQUIRED_KEYS = {'type', 'id', 'title', 'subtitle', 'url'}


@pytest.mark.django_db
class TestAdminGlobalSearch(TestCase):
    """Endpoint: GET /api/v1/admin/search."""

    URL = '/api/v1/admin/search'

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='search-admin@example.com',
            username='search-admin',
            password='testpass123',
            role='admin',
        )
        self.trainer = User.objects.create_user(
            email='search-trainer@example.com',
            username='search-trainer',
            password='testpass123',
            role='trainer',
        )
        self.reviewer = User.objects.create_user(
            email='search-reviewer@example.com',
            username='search-reviewer',
            password='testpass123',
            role='reviewer',
        )
        self.qa_lead = User.objects.create_user(
            email='search-qa@example.com',
            username='search-qa',
            password='testpass123',
            role='qa_lead',
        )

    # ---------------- access control ----------------

    def test_admin_gets_200(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL, {'q': 'Geeta'})
        self.assertEqual(resp.status_code, 200)

    def test_trainer_gets_403(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(self.URL, {'q': 'Geeta'})
        self.assertEqual(resp.status_code, 403)

    def test_reviewer_gets_403(self):
        self.client.force_authenticate(user=self.reviewer)
        resp = self.client.get(self.URL, {'q': 'Geeta'})
        self.assertEqual(resp.status_code, 403)

    def test_qa_lead_gets_403(self):
        self.client.force_authenticate(user=self.qa_lead)
        resp = self.client.get(self.URL, {'q': 'Geeta'})
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_gets_401_or_403(self):
        resp = self.client.get(self.URL, {'q': 'Geeta'})
        self.assertIn(resp.status_code, (401, 403))

    # ---------------- empty query handling ----------------

    def test_empty_q_returns_empty_list(self):
        """Empty `q` → 200 with [] — NOT 400. Palette opens empty."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_explicit_empty_q_returns_empty_list(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL, {'q': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_whitespace_q_returns_empty_list(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL, {'q': '   '})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    # ---------------- match semantics ----------------

    def test_q_geeta_returns_trainer_geeta(self):
        """`q=Geeta` matches trainer Geeta Parihar by name."""
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'Geeta'}).json()
        self.assertGreater(len(body), 0)
        # At least one trainer row whose title contains "Geeta"
        trainer_hits = [r for r in body if r['type'] == 'trainer' and 'Geeta' in r['title']]
        self.assertGreater(len(trainer_hits), 0)
        self.assertEqual(trainer_hits[0]['id'], 5)
        self.assertEqual(trainer_hits[0]['url'], '/admin/trainers/5')

    def test_q_case_insensitive(self):
        """`q=geeta` (lowercase) matches the same row as `q=Geeta`."""
        self.client.force_authenticate(user=self.admin)
        lower = self.client.get(self.URL, {'q': 'geeta'}).json()
        upper = self.client.get(self.URL, {'q': 'GEETA'}).json()
        self.assertEqual(
            {r['id'] for r in lower},
            {r['id'] for r in upper},
            'Case should not affect match set.',
        )

    def test_q_hindi_returns_mixed_types(self):
        """`q=hindi` should hit at least 2 distinct result types."""
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'hindi'}).json()
        self.assertGreater(len(body), 0)
        types_seen = {r['type'] for r in body}
        self.assertGreaterEqual(
            len(types_seen),
            2,
            f'Expected mixed types for `hindi`, got: {types_seen}',
        )

    def test_q_no_match_returns_empty(self):
        """A nonsense needle returns [] (not 404)."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL, {'q': 'qqqzzzxxxneverexists'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    # ---------------- scope filters ----------------

    def test_scope_trainers_returns_only_trainers(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'hindi', 'scope': 'trainers'}).json()
        self.assertGreater(len(body), 0)
        for row in body:
            self.assertEqual(row['type'], 'trainer')

    def test_scope_projects_returns_only_projects(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'hindi', 'scope': 'projects'}).json()
        self.assertGreater(len(body), 0)
        for row in body:
            self.assertEqual(row['type'], 'project')

    def test_scope_submissions_returns_only_submissions(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'hindi', 'scope': 'submissions'}).json()
        self.assertGreater(len(body), 0)
        for row in body:
            self.assertEqual(row['type'], 'submission')

    def test_scope_audit_logs_returns_only_audit(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'login', 'scope': 'audit_logs'}).json()
        self.assertGreater(len(body), 0)
        for row in body:
            self.assertEqual(row['type'], 'audit')

    def test_scope_tasks_returns_only_tasks(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'task', 'scope': 'tasks'}).json()
        self.assertGreater(len(body), 0)
        for row in body:
            self.assertEqual(row['type'], 'task')

    def test_scope_all_returns_mixed_types(self):
        """Default scope `all` should mix types when the needle is broad."""
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'hindi', 'scope': 'all'}).json()
        self.assertGreater(len(body), 0)
        types_seen = {r['type'] for r in body}
        self.assertGreater(len(types_seen), 1)

    def test_unknown_scope_falls_back_to_all(self):
        """Garbage scope value silently treated as `all` — no 400."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL, {'q': 'hindi', 'scope': 'banana'})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertGreater(len(body), 0)

    def test_default_scope_is_all(self):
        """No `scope` param == `scope=all`."""
        self.client.force_authenticate(user=self.admin)
        no_scope = self.client.get(self.URL, {'q': 'hindi'}).json()
        all_scope = self.client.get(self.URL, {'q': 'hindi', 'scope': 'all'}).json()
        self.assertEqual(
            {(r['type'], r['id']) for r in no_scope},
            {(r['type'], r['id']) for r in all_scope},
        )

    # ---------------- per-row shape contract ----------------

    def test_response_is_flat_array(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'hindi'}).json()
        self.assertIsInstance(body, list)

    def test_each_row_has_required_keys(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'hindi'}).json()
        self.assertGreater(len(body), 0)
        for row in body:
            missing = _REQUIRED_KEYS - set(row.keys())
            self.assertFalse(missing, f'Row missing keys: {missing} (row={row})')

    def test_each_row_type_is_known(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'hindi'}).json()
        for row in body:
            self.assertIn(row['type'], _VALID_TYPES)

    def test_each_row_url_is_admin_route(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'hindi'}).json()
        for row in body:
            self.assertTrue(
                row['url'].startswith('/admin/'),
                f'URL should be an /admin/ route — got {row["url"]!r}',
            )

    def test_internal_search_field_not_leaked(self):
        """The mock dataset's `_search` corpus must NEVER reach the client."""
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'hindi'}).json()
        for row in body:
            self.assertNotIn('_search', row, '_search field must be stripped')

    # ---------------- max-50 cap ----------------

    def test_max_50_results_enforced(self):
        """Hard cap at 50 — even an extremely broad needle returns ≤ 50."""
        self.client.force_authenticate(user=self.admin)
        # Single-char vowel matches a lot of seed rows — exercises the cap path.
        body = self.client.get(self.URL, {'q': 'a'}).json()
        self.assertLessEqual(len(body), 50)

    def test_max_50_results_enforced_scope_all(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'i', 'scope': 'all'}).json()
        self.assertLessEqual(len(body), 50)

    # ---------------- specific seed lookups (regression guard) ----------------

    def test_q_rajasthan_returns_geeta(self):
        """`q=Rajasthan` should match Geeta's state subtitle."""
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'Rajasthan'}).json()
        ids = {r['id'] for r in body if r['type'] == 'trainer'}
        self.assertIn(5, ids)

    def test_q_kyc_returns_project_and_task(self):
        """`q=KYC` should hit the KYC OCR project and the KYC task."""
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'q': 'KYC'}).json()
        types_seen = {r['type'] for r in body}
        self.assertIn('project', types_seen)
        # Task #7012 is KYC OCR Aadhaar front
        task_ids = {r['id'] for r in body if r['type'] == 'task'}
        self.assertIn(7012, task_ids)
