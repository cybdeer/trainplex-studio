"""Tests for the TrainPlex admin submissions-preview endpoint.

Phase 1 Step 4.2-9.

Covers
------
- Admin role gets a 200 with the expected JSON shape.
- Trainer role is rejected with 403.
- Unauthenticated request rejected (401 or 403, both acceptable).
- ``limit`` default of 10 honoured when no query is passed.
- ``limit`` capped at 50 when caller asks for more (1000 → 50).
- ``limit`` non-positive / garbage → fallback to 10.
- ``project_id`` / ``trainer_id`` / ``status`` filters narrow the list.
- Filter combo (project_id + status) narrows further than either alone.
- Garbage filters silently ignored — no 400, baseline rows returned.
- Each entry carries the required keys / shape contract.
- ``reviewer_scores`` is always a 3-element list.
- Truncation: ``task_preview`` and ``answer_preview`` never exceed 200 chars.
- ``created_at`` ends in ``Z`` (so the React `new Date(...)` works).

Real data wiring is Phase 2 (Step 8). This file pins the contract so the
frontend stays stable across the swap.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestAdminSubmissionsPreview(TestCase):
    """Endpoint: GET /api/v1/admin/submissions/preview."""

    URL = '/api/v1/admin/submissions/preview'

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='preview-admin@example.com',
            username='preview-admin',
            password='testpass123',
            role='admin',
        )
        self.trainer = User.objects.create_user(
            email='preview-trainer@example.com',
            username='preview-trainer',
            password='testpass123',
            role='trainer',
        )

    # ---------------- access control ----------------

    def test_admin_gets_200(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)

    def test_trainer_gets_403(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_gets_401_or_403(self):
        resp = self.client.get(self.URL)
        self.assertIn(resp.status_code, (401, 403))

    # ---------------- top-level shape ----------------

    def test_top_level_keys(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        self.assertEqual(
            set(body.keys()),
            {'as_of', 'limit', 'filters', 'submissions'},
        )

    def test_as_of_is_iso8601_zulu(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        self.assertTrue(body['as_of'].endswith('Z'))
        self.assertIn('T', body['as_of'])

    # ---------------- limit semantics ----------------

    def test_default_limit_is_10(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        self.assertEqual(body['limit'], 10)
        self.assertLessEqual(len(body['submissions']), 10)

    def test_explicit_limit_honoured(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'limit': 5}).json()
        self.assertEqual(body['limit'], 5)
        self.assertEqual(len(body['submissions']), 5)

    def test_limit_above_50_capped(self):
        """Cap is 50 — asking for 1000 should yield ≤ 50 and limit == 50."""
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'limit': 1000}).json()
        self.assertEqual(body['limit'], 50)
        self.assertLessEqual(len(body['submissions']), 50)

    def test_limit_zero_or_negative_falls_back_to_default(self):
        self.client.force_authenticate(user=self.admin)
        for v in ('0', '-3', 'banana'):
            body = self.client.get(self.URL, {'limit': v}).json()
            self.assertEqual(body['limit'], 10, f'limit={v!r} should fall back to 10')

    # ---------------- filters ----------------

    def test_filter_project_id_narrows(self):
        """Filtering by project_id should be a strict subset."""
        self.client.force_authenticate(user=self.admin)
        # First, find a project_id that exists in the unfiltered mock.
        all_body = self.client.get(self.URL, {'limit': 50}).json()
        project_ids = {s['project_id'] for s in all_body['submissions']}
        self.assertTrue(project_ids, 'mock should expose at least one project_id')
        target = next(iter(project_ids))

        filtered = self.client.get(self.URL, {'project_id': target, 'limit': 50}).json()
        self.assertEqual(filtered['filters'].get('project_id'), target)
        for row in filtered['submissions']:
            self.assertEqual(row['project_id'], target)

    def test_filter_trainer_id_narrows(self):
        self.client.force_authenticate(user=self.admin)
        all_body = self.client.get(self.URL, {'limit': 50}).json()
        trainer_ids = {s['trainer']['id'] for s in all_body['submissions']}
        self.assertTrue(trainer_ids)
        target = next(iter(trainer_ids))

        filtered = self.client.get(self.URL, {'trainer_id': target, 'limit': 50}).json()
        self.assertEqual(filtered['filters'].get('trainer_id'), target)
        for row in filtered['submissions']:
            self.assertEqual(row['trainer']['id'], target)

    def test_filter_status_narrows(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'status': 'approved', 'limit': 50}).json()
        self.assertEqual(body['filters'].get('status'), 'approved')
        for row in body['submissions']:
            self.assertEqual(row['status'], 'approved')

    def test_filter_combo_narrows_further(self):
        """project_id + status combined should be tighter than status alone."""
        self.client.force_authenticate(user=self.admin)
        status_only = self.client.get(self.URL, {'status': 'submitted', 'limit': 50}).json()
        project_ids = {s['project_id'] for s in status_only['submissions']}
        self.assertTrue(project_ids)
        target = next(iter(project_ids))

        combo = self.client.get(
            self.URL,
            {'status': 'submitted', 'project_id': target, 'limit': 50},
        ).json()
        # Every row passes both predicates.
        for row in combo['submissions']:
            self.assertEqual(row['status'], 'submitted')
            self.assertEqual(row['project_id'], target)
        # And the combo set is ≤ the status-only set.
        self.assertLessEqual(len(combo['submissions']), len(status_only['submissions']))

    def test_garbage_filters_silently_ignored(self):
        """A typo / unknown status should NOT 400 — it's silently dropped."""
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(
            self.URL,
            {'status': 'NOT_A_REAL_STATUS', 'project_id': 'banana', 'trainer_id': 'x'},
        ).json()
        # No filter echo for any of the garbage params.
        self.assertEqual(body['filters'], {})
        # Default 10 rows returned.
        self.assertGreater(len(body['submissions']), 0)

    # ---------------- per-row shape contract ----------------

    REQUIRED_TOP_KEYS = {
        'id',
        'project_id',
        'trainer',
        'task_preview',
        'answer_preview',
        'reviewer_scores',
        'created_at',
        'status',
    }
    REQUIRED_TRAINER_KEYS = {'id', 'name', 'role'}
    REQUIRED_REVIEWER_SCORE_KEYS = {'reviewer_id', 'score', 'agreed'}

    def test_each_entry_has_required_keys(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL, {'limit': 50}).json()
        self.assertGreater(len(body['submissions']), 0)
        for row in body['submissions']:
            missing = self.REQUIRED_TOP_KEYS - set(row.keys())
            self.assertFalse(missing, f'Row missing keys: {missing}')

            # trainer block
            self.assertIsInstance(row['trainer'], dict)
            tmissing = self.REQUIRED_TRAINER_KEYS - set(row['trainer'].keys())
            self.assertFalse(tmissing, f'Trainer block missing keys: {tmissing}')

            # reviewer_scores must be a 3-element list of typed dicts
            self.assertIsInstance(row['reviewer_scores'], list)
            self.assertEqual(len(row['reviewer_scores']), 3)
            for score in row['reviewer_scores']:
                rmissing = self.REQUIRED_REVIEWER_SCORE_KEYS - set(score.keys())
                self.assertFalse(rmissing, f'reviewer_score missing: {rmissing}')
                self.assertIsInstance(score['reviewer_id'], int)
                self.assertIn(score['score'], (0, 1))
                self.assertIsInstance(score['agreed'], bool)

            # preview truncation invariant — never exceeds 200 chars
            self.assertLessEqual(len(row['task_preview']), 200)
            self.assertLessEqual(len(row['answer_preview']), 200)

            # created_at always ISO-Z so frontend `new Date(...)` works
            self.assertTrue(row['created_at'].endswith('Z'))
            self.assertIn('T', row['created_at'])

            # status is one of the 4 known values
            self.assertIn(
                row['status'],
                ('submitted', 'under_review', 'approved', 'rejected'),
            )
