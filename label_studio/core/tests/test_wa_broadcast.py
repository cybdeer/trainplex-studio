"""Tests for the TrainPlex admin WhatsApp Broadcast endpoints.

Phase 1 Step 4.2-7.

Covers:
- GET /api/v1/admin/wa/templates — admin gets 5 templates with en+hi.
- POST /api/v1/admin/wa/broadcast — admin can broadcast; AiSensy is mocked.
- Trainer is rejected with 403 on all three endpoints (RBAC).
- Bad template_id → 400.
- Empty trainer_ids → 400.
- Idempotency: same (template, trainer) within 60s = second call's row is
  marked status=skipped.
- Founder personal mobile (sourced from TRAINPLEX_FOUNDER_MOBILE_GUARD) NEVER appears in any logged params
  or request/response body — regex assertion across stored rows.
- History endpoint returns the last 100 rows admin-only.

The AiSensy outbound is patched via `unittest.mock` so no real HTTP fires.
"""

from __future__ import annotations

import os
import re
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models_broadcast import WhatsAppBroadcastLog
from core.services import wa_broadcast as wa_svc

User = get_user_model()

# Leak-check helpers. The digits come from the
# ``TRAINPLEX_FOUNDER_MOBILE_GUARD`` env var via
# ``core.services.founder_guard``; we delegate so this test file contains
# no literal of the founder's mobile.
from core.services.founder_guard import (  # noqa: E402
    assert_no_founder_number as _guard_assert,
    build_guard_pattern as _guard_build_pattern,
    digits_only as _guard_digits_only,
    get_guard_digits_with_cc as _guard_with_cc,
)

FOUNDER_DIGITS = _guard_with_cc()
FOUNDER_LEAK_RE = _guard_build_pattern()


def _assert_no_founder_number(haystack: str, context: str = '') -> None:
    """Fail if the founder's personal mobile appears in `haystack`."""
    digits = _guard_digits_only(haystack)
    assert FOUNDER_DIGITS and FOUNDER_DIGITS not in digits, (
        f'Founder number leaked in {context}: {haystack!r}'
    )
    if FOUNDER_LEAK_RE is not None:
        assert not FOUNDER_LEAK_RE.search(haystack or ''), (
            f'Founder number leaked in {context}: {haystack!r}'
        )


@pytest.mark.django_db
class TestAdminWhatsAppBroadcast(TestCase):
    """Endpoints: /api/v1/admin/wa/{templates, broadcast, broadcast/history}."""

    URL_TEMPLATES = '/api/v1/admin/wa/templates'
    URL_BROADCAST = '/api/v1/admin/wa/broadcast'
    URL_HISTORY = '/api/v1/admin/wa/broadcast/history'

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='wa-admin@example.com',
            username='wa-admin',
            password='testpass123',
            role='admin',
        )
        self.trainer = User.objects.create_user(
            email='wa-trainer@example.com',
            username='wa-trainer',
            password='testpass123',
            role='trainer',
            phone='+91 90000 00001',
        )
        self.trainer2 = User.objects.create_user(
            email='wa-trainer2@example.com',
            username='wa-trainer2',
            password='testpass123',
            role='trainer',
            phone='+91 90000 00002',
        )

    # =============================================================
    # GET /api/v1/admin/wa/templates
    # =============================================================

    def test_templates_admin_gets_200_with_five_templates(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_TEMPLATES)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['count'], 5)
        ids = {t['id'] for t in body['items']}
        self.assertEqual(
            ids,
            {'bronze_passed', 'welcome', 'reminder', 'payment_released', 'task_assigned'},
        )

    def test_templates_each_has_en_and_hi(self):
        self.client.force_authenticate(user=self.admin)
        items = self.client.get(self.URL_TEMPLATES).json()['items']
        for t in items:
            self.assertTrue(t['title_en'], f'{t["id"]} missing en title')
            self.assertTrue(t['title_hi'], f'{t["id"]} missing hi title')
            self.assertTrue(t['description_en'])
            self.assertTrue(t['description_hi'])

    def test_templates_trainer_gets_403(self):
        self.client.force_authenticate(user=self.trainer)
        self.assertEqual(self.client.get(self.URL_TEMPLATES).status_code, 403)

    # =============================================================
    # POST /api/v1/admin/wa/broadcast — happy path
    # =============================================================

    def test_broadcast_admin_succeeds_with_mocked_aisensy(self):
        self.client.force_authenticate(user=self.admin)
        with patch.object(
            wa_svc,
            '_send_aisensy_template',
            wraps=wa_svc._send_aisensy_template,
        ) as send_spy:
            resp = self.client.post(
                self.URL_BROADCAST,
                data={
                    'template_id': 'welcome',
                    'trainer_ids': [self.trainer.id, self.trainer2.id],
                },
                format='json',
            )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['counts']['sent'], 2)
        self.assertEqual(body['counts']['failed'], 0)
        self.assertEqual(body['counts']['skipped'], 0)
        self.assertEqual(body['counts']['total'], 2)
        # Spy fired twice (once per trainer).
        self.assertEqual(send_spy.call_count, 2)
        # And rows landed in DB.
        self.assertEqual(WhatsAppBroadcastLog.objects.filter(status='sent').count(), 2)

    # =============================================================
    # Access control
    # =============================================================

    def test_broadcast_trainer_gets_403(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.post(
            self.URL_BROADCAST,
            data={'template_id': 'welcome', 'trainer_ids': [self.trainer2.id]},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_broadcast_unauthenticated_rejected(self):
        resp = self.client.post(
            self.URL_BROADCAST,
            data={'template_id': 'welcome', 'trainer_ids': [self.trainer.id]},
            format='json',
        )
        self.assertIn(resp.status_code, (401, 403))

    # =============================================================
    # Validation
    # =============================================================

    def test_broadcast_unknown_template_id_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BROADCAST,
            data={'template_id': 'not_a_template', 'trainer_ids': [self.trainer.id]},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertIn('Unknown template_id', body['error'])

    def test_broadcast_missing_template_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BROADCAST,
            data={'trainer_ids': [self.trainer.id]},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'template_id')

    def test_broadcast_empty_trainer_ids_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BROADCAST,
            data={'template_id': 'welcome', 'trainer_ids': []},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'trainer_ids')

    def test_broadcast_non_int_trainer_ids_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BROADCAST,
            data={'template_id': 'welcome', 'trainer_ids': ['abc', None]},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'trainer_ids')

    # =============================================================
    # Idempotency — second same-template send to same trainer = skipped
    # =============================================================

    def test_broadcast_dedupes_same_template_same_trainer_within_60s(self):
        self.client.force_authenticate(user=self.admin)
        # First broadcast — should land as sent.
        resp1 = self.client.post(
            self.URL_BROADCAST,
            data={'template_id': 'welcome', 'trainer_ids': [self.trainer.id]},
            format='json',
        )
        self.assertEqual(resp1.json()['counts']['sent'], 1)
        # Second broadcast immediately after — same (template, trainer) ⇒ skipped.
        resp2 = self.client.post(
            self.URL_BROADCAST,
            data={'template_id': 'welcome', 'trainer_ids': [self.trainer.id]},
            format='json',
        )
        body2 = resp2.json()
        self.assertEqual(body2['counts']['sent'], 0)
        self.assertEqual(body2['counts']['skipped'], 1)
        # Both rows exist on the log.
        rows = WhatsAppBroadcastLog.objects.filter(
            template_id='welcome', trainer_user=self.trainer
        ).order_by('id')
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows[0].status, 'sent')
        self.assertEqual(rows[1].status, 'skipped')

    def test_broadcast_different_template_not_deduped(self):
        """Different template to same trainer is NOT a duplicate."""
        self.client.force_authenticate(user=self.admin)
        self.client.post(
            self.URL_BROADCAST,
            data={'template_id': 'welcome', 'trainer_ids': [self.trainer.id]},
            format='json',
        )
        resp = self.client.post(
            self.URL_BROADCAST,
            data={'template_id': 'reminder', 'trainer_ids': [self.trainer.id]},
            format='json',
        )
        self.assertEqual(resp.json()['counts']['sent'], 1)
        self.assertEqual(resp.json()['counts']['skipped'], 0)

    def test_broadcast_outside_window_not_deduped(self):
        """A send older than the dedup window is not counted as duplicate."""
        # Plant a 'sent' row 5 minutes ago.
        old = WhatsAppBroadcastLog.objects.create(
            admin=self.admin,
            template_id='welcome',
            trainer_user=self.trainer,
            trainer_id_value=self.trainer.id,
            mobile_number=self.trainer.phone,
            params={},
            status='sent',
        )
        # Backdate created_at past the window.
        WhatsAppBroadcastLog.objects.filter(id=old.id).update(
            created_at=timezone.now() - timedelta(minutes=5)
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BROADCAST,
            data={'template_id': 'welcome', 'trainer_ids': [self.trainer.id]},
            format='json',
        )
        self.assertEqual(resp.json()['counts']['sent'], 1)
        self.assertEqual(resp.json()['counts']['skipped'], 0)

    # =============================================================
    # Founder personal mobile — defensive check
    # =============================================================

    def test_founder_personal_number_never_appears_in_any_payload(self):
        """The founder personal mobile must not appear in any params, log, or response body."""
        self.client.force_authenticate(user=self.admin)
        # Innocuous params that the admin might attach in real usage.
        resp = self.client.post(
            self.URL_BROADCAST,
            data={
                'template_id': 'payment_released',
                'trainer_ids': [self.trainer.id, self.trainer2.id],
                'custom_params': {
                    str(self.trainer.id): {'name': 'Geeta P.', 'amount': 4350},
                    str(self.trainer2.id): {'name': 'Sunil M.', 'amount': 4100},
                },
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        # Response body must not include the founder's number anywhere.
        _assert_no_founder_number(resp.content.decode('utf-8'), 'response body')
        # And every persisted row must be clean.
        for row in WhatsAppBroadcastLog.objects.all():
            _assert_no_founder_number(row.mobile_number, f'log row {row.id} mobile')
            _assert_no_founder_number(str(row.params), f'log row {row.id} params')

    def test_service_rejects_founder_number_in_params(self):
        """If a buggy caller passes the founder number in params, the service raises."""
        with self.assertRaises(ValueError):
            wa_svc.send_template_to_trainers(
                template_id='welcome',
                trainer_ids=[self.trainer.id],
                params_per_trainer={
                    self.trainer.id: {'message': 'Contact founder at 8764 001 234'},
                },
                admin_user=self.admin,
            )

    # =============================================================
    # History endpoint
    # =============================================================

    def test_history_admin_lists_recent_rows(self):
        self.client.force_authenticate(user=self.admin)
        self.client.post(
            self.URL_BROADCAST,
            data={'template_id': 'welcome', 'trainer_ids': [self.trainer.id, self.trainer2.id]},
            format='json',
        )
        resp = self.client.get(self.URL_HISTORY)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['count'], 2)
        statuses = {row['status'] for row in body['items']}
        self.assertEqual(statuses, {'sent'})

    def test_history_trainer_gets_403(self):
        self.client.force_authenticate(user=self.trainer)
        self.assertEqual(self.client.get(self.URL_HISTORY).status_code, 403)

    # =============================================================
    # Rate limit — 3 broadcasts per hour per admin
    # =============================================================

    def test_broadcast_rate_limited_after_three_bursts(self):
        self.client.force_authenticate(user=self.admin)
        # Plant 3 rows that look like 3 distinct broadcast bursts (created >2s apart).
        now = timezone.now()
        for i in range(3):
            row = WhatsAppBroadcastLog.objects.create(
                admin=self.admin,
                template_id='welcome',
                trainer_user=self.trainer,
                trainer_id_value=self.trainer.id,
                mobile_number=self.trainer.phone,
                params={},
                status='sent',
            )
            WhatsAppBroadcastLog.objects.filter(id=row.id).update(
                created_at=now - timedelta(minutes=10 * (i + 1))
            )
        resp = self.client.post(
            self.URL_BROADCAST,
            data={'template_id': 'reminder', 'trainer_ids': [self.trainer2.id]},
            format='json',
        )
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.json()['code'], 'rate_limited')

    # =============================================================
    # Trainer with no phone → failed row (not silent skip)
    # =============================================================

    def test_trainer_without_phone_marked_failed(self):
        no_phone = User.objects.create_user(
            email='noPhone@example.com',
            username='noPhone',
            password='testpass123',
            role='trainer',
            phone='',
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self.URL_BROADCAST,
            data={'template_id': 'welcome', 'trainer_ids': [no_phone.id]},
            format='json',
        )
        body = resp.json()
        self.assertEqual(body['counts']['sent'], 0)
        self.assertEqual(body['counts']['failed'], 1)
        row = WhatsAppBroadcastLog.objects.get(trainer_user=no_phone)
        self.assertEqual(row.status, 'failed')
        self.assertIn('no mobile number', row.error)
