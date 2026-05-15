"""Tests for the TrainPlex Trainer Batch endpoint — Phase 1 Step 1.4-E.

Endpoints
---------
GET  /api/v1/trainer/batch
POST /api/v1/trainer/batch/refresh

Coverage
--------
- Trainer GET returns 200 + exactly the requested batch size (default 10).
- Trainer GET defaults to 10 with no ``size`` param.
- Trainer GET ``size`` is hard-capped at MAX_BATCH_SIZE (50).
- Trainer GET ``size`` falls back to default on non-numeric input.
- Reviewer GET returns 403 (role-gated).
- Admin GET returns 403 (trainer-only surface — admin has bulk-assign instead).
- Unauthenticated GET returns 401/403 (DRF IsAuthenticated).
- Admin POST refresh returns 200 + a fresh batch (and a refreshed_count).
- Trainer POST refresh returns 403 (admin-only).
- Per-trainer determinism: two GETs return the same batch for the same trainer.
- Per-trainer distinctness: two different trainers see different mock tasks.
- Each row carries the contract keys (task_id, project_id, task_type, …).

Tests intentionally hit the URL directly (not by name) so a refactor in
``core/urls.py`` is caught immediately by the test.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


URL = '/api/v1/trainer/batch'
REFRESH_URL = '/api/v1/trainer/batch/refresh'

# Pinned from tasks.api_batch — duplicated here so a contract-changing edit
# fails this test, not silently passes.
DEFAULT_BATCH_SIZE = 10
MAX_BATCH_SIZE = 50

ROW_KEYS = {
    'task_id',
    'project_id',
    'task_type',
    'preview',
    'earnings_inr',
    'estimated_min',
    'tier',
    'status',
}


@pytest.mark.django_db
class TestTrainerBatchAPI(TestCase):
    """Endpoint: GET /api/v1/trainer/batch."""

    def setUp(self):
        self.client = APIClient()
        self.trainer = User.objects.create_user(
            email='batch-trainer@example.com',
            username='batch-trainer',
            password='testpass123',
            role='trainer',
        )
        self.trainer_b = User.objects.create_user(
            email='batch-trainer-b@example.com',
            username='batch-trainer-b',
            password='testpass123',
            role='trainer',
        )
        self.reviewer = User.objects.create_user(
            email='batch-reviewer@example.com',
            username='batch-reviewer',
            password='testpass123',
            role='reviewer',
        )
        self.admin = User.objects.create_user(
            email='batch-admin@example.com',
            username='batch-admin',
            password='testpass123',
            role='admin',
        )

    # ------- happy path -------

    def test_trainer_get_returns_default_10_tasks(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), DEFAULT_BATCH_SIZE)

    def test_trainer_get_returns_contract_keys_per_row(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(URL)
        body = resp.json()
        for row in body:
            missing = ROW_KEYS - set(row.keys())
            self.assertFalse(missing, f'Row missing keys: {missing}; got {set(row.keys())}')
            self.assertIn(row['status'], {'pending', 'in_progress', 'done'})
            self.assertIsInstance(row['earnings_inr'], int)
            self.assertIsInstance(row['estimated_min'], int)
            self.assertGreater(row['earnings_inr'], 0)

    def test_trainer_get_with_explicit_size_returns_that_many(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(URL, {'size': 5})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 5)

    def test_trainer_get_size_above_max_is_capped(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(URL, {'size': 9999})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), MAX_BATCH_SIZE)

    def test_trainer_get_non_numeric_size_falls_back_to_default(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(URL, {'size': 'abc'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), DEFAULT_BATCH_SIZE)

    def test_trainer_get_zero_size_falls_back_to_default(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(URL, {'size': 0})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), DEFAULT_BATCH_SIZE)

    # ------- determinism + isolation -------

    def test_trainer_get_is_deterministic_for_same_trainer(self):
        self.client.force_authenticate(user=self.trainer)
        first = self.client.get(URL).json()
        second = self.client.get(URL).json()
        self.assertEqual(first, second)

    def test_trainer_get_is_distinct_across_trainers(self):
        self.client.force_authenticate(user=self.trainer)
        a = self.client.get(URL).json()
        self.client.force_authenticate(user=self.trainer_b)
        b = self.client.get(URL).json()
        # task_ids encode user_id so they MUST differ across users.
        ids_a = sorted(r['task_id'] for r in a)
        ids_b = sorted(r['task_id'] for r in b)
        self.assertNotEqual(ids_a, ids_b)

    # ------- role gating -------

    def test_reviewer_get_returns_403(self):
        self.client.force_authenticate(user=self.reviewer)
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 403)

    def test_admin_get_returns_403(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_get_is_denied(self):
        resp = self.client.get(URL)
        # DRF default for IsAuthenticated is 401 (with auth header) or 403 —
        # we accept either so the test isn't tied to the auth middleware.
        self.assertIn(resp.status_code, (401, 403))

    # ------- refresh endpoint -------

    def test_admin_refresh_returns_fresh_batch(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(REFRESH_URL, data={'trainer_id': self.trainer.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['trainer_id'], self.trainer.id)
        self.assertEqual(body['refreshed_count'], DEFAULT_BATCH_SIZE)
        self.assertEqual(len(body['batch']), DEFAULT_BATCH_SIZE)

    def test_admin_refresh_with_size_caps_at_max(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(REFRESH_URL, data={'size': 200}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['batch']), MAX_BATCH_SIZE)

    def test_trainer_refresh_returns_403(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.post(REFRESH_URL, data={}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_reviewer_refresh_returns_403(self):
        self.client.force_authenticate(user=self.reviewer)
        resp = self.client.post(REFRESH_URL, data={}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_admin_refresh_with_bad_trainer_id_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            REFRESH_URL, data={'trainer_id': 'not-an-int'}, format='json'
        )
        self.assertEqual(resp.status_code, 400)
