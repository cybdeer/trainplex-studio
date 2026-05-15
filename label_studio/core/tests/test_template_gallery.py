"""Tests for the TrainPlex admin template catalog endpoint.

Phase 1 Step 4.2-2.

Covers:
- Admin role gets a 200 with merged catalog (>=10 templates).
- Trainer role gets 403.
- Each template card carries the required keys (id, title, category, …).
- TrainPlex India templates are marked ``trainplex_custom=true``.
- LS native templates are marked ``trainplex_custom=false``.
- Both buckets surface in ``trainplex_count`` / ``native_count`` totals.

Real Phase-2 template loading (full label_config XML) lands in a later step.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestAdminTemplateCatalog(TestCase):
    """Endpoint: GET /api/v1/admin/templates/catalog."""

    URL = '/api/v1/admin/templates/catalog'

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='tpl-admin@example.com',
            username='tpl-admin',
            password='testpass123',
            role='admin',
        )
        self.trainer = User.objects.create_user(
            email='tpl-trainer@example.com',
            username='tpl-trainer',
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

    def test_unauthenticated_rejected(self):
        resp = self.client.get(self.URL)
        self.assertIn(resp.status_code, (401, 403))

    # ---------------- shape contract ----------------

    def test_response_has_expected_top_level_keys(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        self.assertEqual(
            set(body.keys()),
            {'count', 'trainplex_count', 'native_count', 'items'},
        )

    def test_returns_at_least_10_templates(self):
        """10 TrainPlex India + 50 LS native should be >= 10 always."""
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        self.assertGreaterEqual(body['count'], 10)
        self.assertEqual(body['count'], len(body['items']))

    def test_count_split_matches_buckets(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        self.assertEqual(body['count'], body['trainplex_count'] + body['native_count'])

    def test_native_template_count_is_50(self):
        """LS native list is hardcoded — pin the count so we notice drift."""
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(self.URL).json()
        self.assertEqual(body['native_count'], 50)

    def test_each_template_has_required_keys(self):
        self.client.force_authenticate(user=self.admin)
        items = self.client.get(self.URL).json()['items']
        required = {
            'id',
            'title',
            'title_hi',
            'category',
            'description',
            'description_hi',
            'india_relevance',
            'thumbnail_url',
            'tier',
            'trainplex_custom',
        }
        for item in items:
            self.assertTrue(
                required.issubset(item.keys()),
                f'Template {item.get("id")} missing keys: '
                f'{required - set(item.keys())}',
            )

    def test_trainplex_custom_flag_correctness(self):
        """India bucket = True, native bucket = False (no overlap)."""
        self.client.force_authenticate(user=self.admin)
        items = self.client.get(self.URL).json()['items']
        india = [i for i in items if i['trainplex_custom']]
        native = [i for i in items if not i['trainplex_custom']]
        self.assertGreaterEqual(len(india), 1)  # at least one India template
        self.assertGreaterEqual(len(native), 1)
        # All India templates should have a non-empty Devanagari title_hi.
        for t in india:
            self.assertTrue(
                any('ऀ' <= ch <= 'ॿ' for ch in t['title_hi']),
                f'India template {t["id"]} title_hi missing Devanagari: '
                f'{t["title_hi"]!r}',
            )

    def test_template_ids_are_unique(self):
        self.client.force_authenticate(user=self.admin)
        items = self.client.get(self.URL).json()['items']
        ids = [i['id'] for i in items]
        self.assertEqual(
            len(ids), len(set(ids)), 'Duplicate template ids in catalog'
        )

    def test_categories_cover_expected_groups(self):
        """Step 2.1 categories should all surface in the native bucket."""
        self.client.force_authenticate(user=self.admin)
        items = self.client.get(self.URL).json()['items']
        cats = {i['category'] for i in items if not i['trainplex_custom']}
        expected = {
            'Text / NLP',
            'Image',
            'Audio',
            'Video',
            'Conversational',
            'LLM',
            'Structured',
            'TimeSeries',
            'Ranking',
        }
        self.assertTrue(
            expected.issubset(cats),
            f'Missing categories: {expected - cats}',
        )
