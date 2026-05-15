"""Tests for the TrainPlex admin Project Wizard create endpoint.

Phase 1 Step 4.2-2.

Covers:
- Admin can POST a valid body and gets a 201 with the new project id + title.
- Trainer is rejected with 403 (RBAC works end-to-end).
- Missing template_id → 400.
- Missing project_name → 400.
- Unknown template_id → 400.
- Bad trainer_ids type → 400.
- Trainer_ids and data_file_upload_id are echoed back as ``_pending`` so the
  founder can see the wizard preserved them — actual wiring is Phase 2.

The endpoint creates a real ``Project`` row so we need an organization in the
test setup. We attach a fresh Organization to each admin user so concurrent
test runs don't clash.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from organizations.models import Organization
from projects.models import Project
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestAdminProjectWizardCreate(TestCase):
    """Endpoint: POST /api/v1/admin/projects/wizard."""

    URL = '/api/v1/admin/projects/wizard'

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='wiz-admin@example.com',
            username='wiz-admin',
            password='testpass123',
            role='admin',
        )
        self.trainer = User.objects.create_user(
            email='wiz-trainer@example.com',
            username='wiz-trainer',
            password='testpass123',
            role='trainer',
        )
        # Admin needs an active organization so Project.create() can FK-ref it.
        self.org = Organization.create_organization(
            created_by=self.admin,
            title='WizardTestOrg',
        )
        self.admin.active_organization = self.org
        self.admin.save()

    # ---------------- access control ----------------

    def test_trainer_gets_403(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.post(
            self.URL,
            data={'template_id': 'text_classification', 'project_name': 'X'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_rejected(self):
        resp = self.client.post(
            self.URL,
            data={'template_id': 'text_classification', 'project_name': 'X'},
            format='json',
        )
        self.assertIn(resp.status_code, (401, 403))

    # ---------------- happy path ----------------

    def test_admin_creates_project_from_native_template(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL,
            data={
                'template_id': 'text_classification',
                'project_name': 'Test Sentiment Batch May 2026',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertIn('id', body)
        self.assertEqual(body['title'], 'Test Sentiment Batch May 2026')
        self.assertEqual(body['template_id'], 'text_classification')
        # Project should actually exist in the DB.
        self.assertTrue(Project.objects.filter(id=body['id']).exists())

    def test_admin_creates_project_from_trainplex_india_template(self):
        """TrainPlex India template_ids must be accepted too — disk-loaded."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL,
            data={
                'template_id': 'aadhaar_ocr_validation',
                'project_name': 'KYC OCR Batch',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['template_id'], 'aadhaar_ocr_validation')

    def test_trainer_ids_echoed_as_pending(self):
        """Phase 1 defers member-add but must round-trip the founder's input."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL,
            data={
                'template_id': 'text_classification',
                'project_name': 'Echo Trainer Ids Project',
                'trainer_ids': [5, 7, 12],
                'data_file_upload_id': 'upload-abc-123',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertEqual(body['trainer_ids_pending'], [5, 7, 12])
        self.assertEqual(body['data_file_upload_id_pending'], 'upload-abc-123')

    # ---------------- validation ----------------

    def test_missing_template_id_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL,
            data={'project_name': 'No Template Project'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'template_id')

    def test_missing_project_name_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL,
            data={'template_id': 'text_classification'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'project_name')

    def test_unknown_template_id_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL,
            data={
                'template_id': 'definitely_not_a_real_template',
                'project_name': 'X',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'template_id')

    def test_bad_trainer_ids_type_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL,
            data={
                'template_id': 'text_classification',
                'project_name': 'Bad Trainers Project',
                'trainer_ids': 'not-a-list',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'trainer_ids')
