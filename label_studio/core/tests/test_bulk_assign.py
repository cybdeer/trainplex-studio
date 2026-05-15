"""Tests for the TrainPlex admin Bulk Task Assign endpoints.

Phase 1 Step 4.2-3.

Endpoints under test:
    GET  /api/v1/admin/trainers/filter
    POST /api/v1/admin/tasks/bulk-assign

Covers:
- Filter by state returns matching trainers (and only those).
- Filter combination (state + tier) intersects correctly.
- Empty / missing filter returns the full roster.
- Filter by language matches trainers whose `languages` list contains the value.
- Filter by cert_passed (tri-state) works for true / false.
- Admin POST with a valid body returns the expected per-trainer counts.
- Tier-weighted strategy gives higher tiers more tasks than bronze.
- Trainer is rejected with 403 on both endpoints (RBAC).
- Missing project_id → 400.
- Non-existing project_id → 400.
- Empty trainer_ids → 400.
- Bad trainer_ids → 400.
- Unknown strategy → 400.
- Rate-limit 429 after 5 successful bursts per hour.

The Phase 1 implementation uses an in-memory roster + an in-memory rate-limit
bucket; the rate-limit cache is reset in setUp so tests stay isolated.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from organizations.models import Organization
from projects.models import Project
from rest_framework.test import APIClient

from core.services import bulk_assign as bulk_svc

User = get_user_model()


@pytest.mark.django_db
class TestAdminBulkAssign(TestCase):
    """Endpoints: GET /trainers/filter + POST /tasks/bulk-assign."""

    URL_FILTER = '/api/v1/admin/trainers/filter'
    URL_BULK = '/api/v1/admin/tasks/bulk-assign'

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='bulk-admin@example.com',
            username='bulk-admin',
            password='testpass123',
            role='admin',
        )
        self.trainer = User.objects.create_user(
            email='bulk-trainer@example.com',
            username='bulk-trainer',
            password='testpass123',
            role='trainer',
        )
        # Org needed for Project.create() FK.
        self.org = Organization.create_organization(
            created_by=self.admin,
            title='BulkAssignTestOrg',
        )
        self.admin.active_organization = self.org
        self.admin.save()
        # Real Project so we have a valid project_id to POST.
        self.project = Project.objects.create(
            title='BulkAssign Test Project',
            created_by=self.admin,
            organization=self.org,
            label_config='<View></View>',
        )
        # Reset in-memory rate-limit cache so each test starts fresh.
        bulk_svc.reset_admin_rate_limit_buckets()

    # =============================================================
    # GET /api/v1/admin/trainers/filter — access + happy paths
    # =============================================================

    def test_filter_trainer_gets_403(self):
        self.client.force_authenticate(user=self.trainer)
        self.assertEqual(self.client.get(self.URL_FILTER).status_code, 403)

    def test_filter_unauthenticated_rejected(self):
        self.assertIn(self.client.get(self.URL_FILTER).status_code, (401, 403))

    def test_filter_empty_returns_full_roster(self):
        """No query params → return every trainer in the in-memory roster."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_FILTER)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        # 12 trainers in the Phase 1 mock roster.
        self.assertEqual(body['count'], 12)
        self.assertEqual(len(body['items']), 12)
        # Every row must carry the trainer-facing fields the bulk-assign UI uses.
        for row in body['items']:
            self.assertIn('id', row)
            self.assertIn('state', row)
            self.assertIn('tier', row)
            self.assertIn('cert_passed', row)
            self.assertIn('current_active_tasks_count', row)

    def test_filter_by_state_returns_matching(self):
        """state=Rajasthan must return only the Rajasthan trainer."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_FILTER, {'state': 'Rajasthan'})
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertGreaterEqual(body['count'], 1)
        for row in body['items']:
            self.assertEqual(row['state'], 'Rajasthan')

    def test_filter_state_multi_value_or_combined(self):
        """state=Rajasthan,UP must return BOTH Rajasthan and UP rows."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_FILTER, {'state': 'Rajasthan,UP'})
        body = resp.json()
        states = {row['state'] for row in body['items']}
        self.assertEqual(states, {'Rajasthan', 'UP'})

    def test_filter_state_and_tier_intersected(self):
        """state=Rajasthan & tier=gold → only the Rajasthan-gold trainer."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(
            self.URL_FILTER, {'state': 'Rajasthan', 'tier': 'gold'}
        )
        body = resp.json()
        for row in body['items']:
            self.assertEqual(row['state'], 'Rajasthan')
            self.assertEqual(row['tier'], 'gold')
        self.assertGreaterEqual(body['count'], 1)

    def test_filter_state_and_tier_no_overlap_returns_empty(self):
        """A state+tier combo no trainer matches must return count=0."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(
            self.URL_FILTER, {'state': 'Rajasthan', 'tier': 'platinum'}
        )
        body = resp.json()
        self.assertEqual(body['count'], 0)
        self.assertEqual(body['items'], [])

    def test_filter_by_language_matches_list_overlap(self):
        """language=Tamil should match the Tamil Nadu / Tamil-speaker trainer."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_FILTER, {'language': 'Tamil'})
        body = resp.json()
        self.assertGreaterEqual(body['count'], 1)
        for row in body['items']:
            self.assertIn('Tamil', row['languages'])

    def test_filter_by_cert_passed_true(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_FILTER, {'cert_passed': 'true'})
        body = resp.json()
        for row in body['items']:
            self.assertTrue(row['cert_passed'])

    def test_filter_by_cert_pending(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_FILTER, {'cert_passed': 'pending'})
        body = resp.json()
        for row in body['items']:
            self.assertFalse(row['cert_passed'])

    # =============================================================
    # POST /api/v1/admin/tasks/bulk-assign — access + happy paths
    # =============================================================

    def test_bulk_assign_trainer_gets_403(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.post(
            self.URL_BULK,
            data={'project_id': self.project.id, 'trainer_ids': [5, 7]},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_bulk_assign_unauthenticated_rejected(self):
        resp = self.client.post(
            self.URL_BULK,
            data={'project_id': self.project.id, 'trainer_ids': [5, 7]},
            format='json',
        )
        self.assertIn(resp.status_code, (401, 403))

    def test_bulk_assign_admin_returns_expected_counts(self):
        """Happy path: 3 trainers × 10 tasks = 30 total, even split."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BULK,
            data={
                'project_id': self.project.id,
                'trainer_ids': [5, 7, 12],
                'tasks_per_trainer': 10,
                'distribute_strategy': 'even',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['strategy'], 'even')
        self.assertEqual(body['tasks_per_trainer'], 10)
        self.assertEqual(len(body['plan']), 3)
        # Every line should have will_assign = 10 in 'even' mode.
        for row in body['plan']:
            self.assertEqual(row['will_assign'], 10)
        self.assertEqual(body['totals']['trainers'], 3)
        self.assertEqual(body['totals']['tasks'], 30)
        self.assertEqual(body['summary']['total_tasks'], 30)

    def test_bulk_assign_default_tasks_per_trainer(self):
        """If tasks_per_trainer is omitted, the service uses 10."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BULK,
            data={'project_id': self.project.id, 'trainer_ids': [5]},
            format='json',
        )
        body = resp.json()
        self.assertEqual(body['tasks_per_trainer'], 10)
        self.assertEqual(body['plan'][0]['will_assign'], 10)

    def test_bulk_assign_tier_weighted_distribution(self):
        """tier-weighted: platinum (id=31) gets >> bronze (id=12)."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BULK,
            data={
                'project_id': self.project.id,
                # 31 = platinum, 5 = gold, 7 = silver, 12 = bronze
                'trainer_ids': [12, 7, 5, 31],
                'tasks_per_trainer': 10,
                'distribute_strategy': 'tier-weighted',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        by_id = {row['trainer_id']: row['will_assign'] for row in body['plan']}
        # Platinum (×2.0) → 20, gold (×1.5) → 15, silver (×1.0) → 10,
        # bronze (×0.5) → 5. Just enforce the ordering invariant so a
        # tweak to the weights doesn't break this test, only changing the
        # ordering would.
        self.assertGreater(by_id[31], by_id[5])
        self.assertGreater(by_id[5], by_id[7])
        self.assertGreater(by_id[7], by_id[12])
        self.assertEqual(body['strategy'], 'tier-weighted')

    def test_bulk_assign_dedups_trainer_ids(self):
        """Duplicates in trainer_ids must collapse into a single plan entry."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BULK,
            data={
                'project_id': self.project.id,
                'trainer_ids': [5, 5, 7, 7, 7, 12],
                'tasks_per_trainer': 4,
            },
            format='json',
        )
        body = resp.json()
        self.assertEqual(len(body['plan']), 3)
        self.assertEqual(body['totals']['trainers'], 3)
        self.assertEqual(body['totals']['tasks'], 12)

    # =============================================================
    # POST validation
    # =============================================================

    def test_bulk_assign_missing_project_id_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BULK,
            data={'trainer_ids': [5, 7]},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'project_id')

    def test_bulk_assign_non_int_project_id_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BULK,
            data={'project_id': 'abc', 'trainer_ids': [5, 7]},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'project_id')

    def test_bulk_assign_nonexistent_project_id_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BULK,
            data={'project_id': 999_999_999, 'trainer_ids': [5, 7]},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'project_id')

    def test_bulk_assign_empty_trainer_ids_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BULK,
            data={'project_id': self.project.id, 'trainer_ids': []},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'trainer_ids')

    def test_bulk_assign_non_list_trainer_ids_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BULK,
            data={'project_id': self.project.id, 'trainer_ids': 'not-a-list'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'trainer_ids')

    def test_bulk_assign_non_int_trainer_ids_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BULK,
            data={'project_id': self.project.id, 'trainer_ids': ['abc']},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'trainer_ids')

    def test_bulk_assign_unknown_strategy_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BULK,
            data={
                'project_id': self.project.id,
                'trainer_ids': [5],
                'distribute_strategy': 'random-pony',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'distribute_strategy')

    def test_bulk_assign_negative_tasks_per_trainer_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BULK,
            data={
                'project_id': self.project.id,
                'trainer_ids': [5],
                'tasks_per_trainer': -3,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'tasks_per_trainer')

    def test_bulk_assign_unknown_trainer_id_is_flagged_not_crashed(self):
        """An id not in the roster is reported in the plan with unknown=True."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BULK,
            data={
                'project_id': self.project.id,
                'trainer_ids': [5, 999_999],
                'tasks_per_trainer': 6,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        unknown_rows = [r for r in body['plan'] if r['unknown']]
        self.assertEqual(len(unknown_rows), 1)
        self.assertEqual(unknown_rows[0]['trainer_id'], 999_999)
        self.assertEqual(unknown_rows[0]['will_assign'], 0)
        self.assertEqual(body['totals']['trainers'], 1)
        self.assertEqual(body['totals']['tasks'], 6)

    # =============================================================
    # Rate limit — 5 successful bulk-assigns / hour / admin
    # =============================================================

    def test_bulk_assign_rate_limited_after_five_bursts(self):
        self.client.force_authenticate(user=self.admin)
        for _ in range(bulk_svc.RATE_LIMIT_BULK_ASSIGN_PER_HOUR):
            resp = self.client.post(
                self.URL_BULK,
                data={
                    'project_id': self.project.id,
                    'trainer_ids': [5],
                    'tasks_per_trainer': 1,
                },
                format='json',
            )
            self.assertEqual(resp.status_code, 200, resp.content)
        # The 6th request hits the cap.
        resp = self.client.post(
            self.URL_BULK,
            data={
                'project_id': self.project.id,
                'trainer_ids': [5],
                'tasks_per_trainer': 1,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.json().get('code'), 'rate_limited')
