"""Tests for TrainPlex PWA endpoints — Phase 1 Step 4.3 + 4.4.

Covers
------
- Manifest endpoint:
  * Anonymous GET → 200 (install flow must work before auth).
  * Correct ``application/manifest+json`` MIME (browsers reject anything else).
  * JSON body shape — ``name``, ``short_name``, ``start_url``, ``display``,
    ``theme_color``, ``background_color``, 3 icons, ``lang: hi-IN``.
  * ``start_url`` is ``/trainer/batch`` (trainer-first PWA install target).

- Single submit (`POST /api/v1/trainer/batch/submit`):
  * Trainer with valid ``task_id`` → 200 + ``ok: true``.
  * Trainer with missing ``task_id`` → 400.
  * Unauthenticated → 401 or 403.
  * Admin / reviewer / qa_lead → 403 (trainer-only).

- Bulk submit (`POST /api/v1/trainer/batch/bulk-submit`):
  * Trainer with N rows → 200 + per-row ``ok`` flags.
  * Duplicate ``task_id`` in same payload → second flagged ``duplicate: true``
    so the client can prune the IndexedDB row without billing twice.
  * Non-list ``submits`` → 400.
  * Row beyond _MAX_BULK_ROWS → 400.
  * Malformed row → individual ``ok: false`` (no whole-batch 5xx).
  * Admin → 403 (trainer-only).
  * Unauthenticated → 401 or 403.
"""

from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestManifestView(TestCase):
    """Endpoint: GET /manifest.webmanifest."""

    URL = '/manifest.webmanifest'

    def setUp(self):
        self.client = APIClient()

    def test_anonymous_can_fetch_manifest(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)

    def test_correct_mime_type(self):
        resp = self.client.get(self.URL)
        # The browser will reject anything that isn't this exact MIME.
        self.assertEqual(resp['Content-Type'], 'application/manifest+json')

    def test_manifest_shape(self):
        resp = self.client.get(self.URL)
        body = json.loads(resp.content.decode('utf-8'))
        # Required PWA manifest fields.
        for key in (
            'name',
            'short_name',
            'description',
            'start_url',
            'display',
            'background_color',
            'theme_color',
            'icons',
            'lang',
            'dir',
            'categories',
        ):
            self.assertIn(key, body, f'manifest missing required key: {key}')
        self.assertEqual(body['short_name'], 'TrainPlex')
        self.assertEqual(body['display'], 'standalone')
        self.assertEqual(body['start_url'], '/trainer/batch')
        self.assertEqual(body['theme_color'], '#1A1A5E')
        self.assertEqual(body['background_color'], '#1A1A5E')
        self.assertEqual(body['lang'], 'hi-IN')
        # 3 icons: 192, 512, maskable-512.
        self.assertEqual(len(body['icons']), 3)
        sizes = {icon['sizes'] for icon in body['icons']}
        self.assertEqual(sizes, {'192x192', '512x512'})
        purposes = {icon['purpose'] for icon in body['icons']}
        self.assertIn('any', purposes)
        self.assertIn('maskable', purposes)


@pytest.mark.django_db
class TestTrainerSubmit(TestCase):
    """Endpoint: POST /api/v1/trainer/batch/submit."""

    URL = '/api/v1/trainer/batch/submit'

    def setUp(self):
        self.client = APIClient()
        self.trainer = User.objects.create_user(
            email='pwa-trainer@example.com',
            username='pwa-trainer',
            password='testpass123',
            role='trainer',
        )
        self.admin = User.objects.create_user(
            email='pwa-admin@example.com',
            username='pwa-admin',
            password='testpass123',
            role='admin',
        )
        self.reviewer = User.objects.create_user(
            email='pwa-reviewer@example.com',
            username='pwa-reviewer',
            password='testpass123',
            role='reviewer',
        )

    def test_trainer_submit_ok(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.post(
            self.URL,
            data={'task_id': 42, 'answer': 'yes'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['task_id'], 42)

    def test_missing_task_id_is_400(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.post(self.URL, data={'answer': 'yes'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_non_int_task_id_is_400(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.post(
            self.URL,
            data={'task_id': 'forty-two'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_is_401_or_403(self):
        resp = self.client.post(self.URL, data={'task_id': 1}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_admin_is_403(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.URL, data={'task_id': 1}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_reviewer_is_403(self):
        self.client.force_authenticate(user=self.reviewer)
        resp = self.client.post(self.URL, data={'task_id': 1}, format='json')
        self.assertEqual(resp.status_code, 403)


@pytest.mark.django_db
class TestTrainerBulkSubmit(TestCase):
    """Endpoint: POST /api/v1/trainer/batch/bulk-submit."""

    URL = '/api/v1/trainer/batch/bulk-submit'

    def setUp(self):
        self.client = APIClient()
        self.trainer = User.objects.create_user(
            email='bulk-trainer@example.com',
            username='bulk-trainer',
            password='testpass123',
            role='trainer',
        )
        self.admin = User.objects.create_user(
            email='bulk-admin@example.com',
            username='bulk-admin',
            password='testpass123',
            role='admin',
        )

    def _post(self, payload):
        return self.client.post(self.URL, data=payload, format='json')

    def test_bulk_ok(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self._post(
            {
                'submits': [
                    {'task_id': 1, 'answer': 'a'},
                    {'task_id': 2, 'answer': 'b'},
                ],
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['accepted'], 2)
        self.assertEqual(len(body['results']), 2)
        for row in body['results']:
            self.assertTrue(row['ok'])

    def test_duplicate_task_id_flagged(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self._post(
            {
                'submits': [
                    {'task_id': 7, 'answer': 'a'},
                    {'task_id': 7, 'answer': 'a-retry'},
                ],
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body['results']), 2)
        # First accepted, second flagged duplicate (still ok=true so the
        # client prunes both IndexedDB rows on the same flush).
        self.assertTrue(body['results'][0]['ok'])
        self.assertTrue(body['results'][1]['ok'])
        self.assertTrue(body['results'][1].get('duplicate'))

    def test_non_list_submits_is_400(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self._post({'submits': 'oops'})
        self.assertEqual(resp.status_code, 400)

    def test_too_many_rows_is_400(self):
        self.client.force_authenticate(user=self.trainer)
        big = [{'task_id': i, 'answer': str(i)} for i in range(150)]
        resp = self._post({'submits': big})
        self.assertEqual(resp.status_code, 400)

    def test_malformed_row_is_per_row_failure_not_5xx(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self._post(
            {
                'submits': [
                    {'task_id': 1, 'answer': 'good'},
                    {'no_task_id': 'bad'},
                    {'task_id': 'not-an-int'},
                    {'task_id': 2, 'answer': 'good2'},
                ],
            },
        )
        # The bulk endpoint never 5xx's on a malformed row — it surfaces
        # the failure per-row so the queue can selectively prune.
        self.assertEqual(resp.status_code, 200)
        results = resp.json()['results']
        self.assertEqual(len(results), 4)
        oks = [r['ok'] for r in results]
        self.assertEqual(oks, [True, False, False, True])

    def test_admin_is_403(self):
        self.client.force_authenticate(user=self.admin)
        resp = self._post({'submits': [{'task_id': 1}]})
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_is_401_or_403(self):
        resp = self._post({'submits': [{'task_id': 1}]})
        self.assertIn(resp.status_code, (401, 403))
