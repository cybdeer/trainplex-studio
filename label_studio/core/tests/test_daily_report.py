"""Tests for the TrainPlex daily founder report email.

Phase 1 Step 4.2-10.

Covers
------
Service (`core/services/daily_report_email.py`):
- `build_daily_summary(date)` returns every documented contract key.
- `build_daily_summary()` with no args defaults to yesterday's date.
- `build_daily_summary('YYYY-MM-DD')` parses an ISO date string.
- `render_email_html(summary)` produces an HTML body with TrainPlex
  Indigo header band + 4-tile KPI grid + top-3-trainers table +
  CTA button pointing at ``/admin/dashboard``.
- Hindi (Devanagari) strings are present in the rendered body —
  parity locked so a future tweak can't accidentally drop the
  bilingual sections.
- `render_email_text(summary)` plain-text fallback is non-empty
  and Hindi text survives.
- `send_daily_report(...)` with the dummy backend (default in tests)
  reports mode=mock and writes a log entry — no real email leaves.
- `send_daily_report(...)` with `dry_run=True` does not call
  `EmailMultiAlternatives.send()`.
- `_assert_no_founder_personal_number(...)` guard raises ValueError
  if the founder's personal mobile shows up in HTML, plain text,
  subject, or recipient string — covers both +91 and no-CC forms.
- Founder personal mobile (sourced from TRAINPLEX_FOUNDER_MOBILE_GUARD) NEVER appears in any rendered
  body or subject of an organic summary.

Management command (`core/management/commands/send_daily_report.py`):
- End-to-end ``send_daily_report --dry-run`` succeeds, does not call
  the email backend's ``send()``, and exits with the success
  stdout marker.
- ``--recipient`` override is honoured.
- ``--date`` with bad format raises CommandError.
- Without ``--recipient`` AND without the env var → CommandError.

These tests pin the Phase 1 contract so the Phase 2 swap (real
submission / payout aggregation in `build_daily_summary`) is a
function-body change, not a public-surface change.
"""

from __future__ import annotations

import re
from datetime import date as _date_type
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core.services import daily_report_email as svc

User = get_user_model()

# The digits come from the ``TRAINPLEX_FOUNDER_MOBILE_GUARD`` env var via
# ``core.services.founder_guard``; we delegate so this test file contains
# no literal of the founder's mobile.
from core.services.founder_guard import (  # noqa: E402
    build_guard_pattern as _guard_build_pattern,
    get_guard_digits_no_cc as _guard_no_cc,
    get_guard_digits_with_cc as _guard_with_cc,
)

FOUNDER_DIGITS_WITH_CC = _guard_with_cc()
FOUNDER_DIGITS_NO_CC = _guard_no_cc()
FOUNDER_LEAK_RE = _guard_build_pattern()


def _assert_no_founder_in(haystack: str, context: str = '') -> None:
    digits = re.sub(r'\D+', '', haystack or '')
    assert FOUNDER_DIGITS_WITH_CC not in digits, (
        f'Founder personal mobile leaked in {context}: {haystack[:200]!r}'
    )
    assert FOUNDER_DIGITS_NO_CC not in digits, (
        f'Founder personal mobile leaked in {context}: {haystack[:200]!r}'
    )
    assert not FOUNDER_LEAK_RE.search(haystack or ''), (
        f'Founder personal mobile leaked in {context}: {haystack[:200]!r}'
    )


# ---------------------------------------------------------------------------
# Pure-Python summary builder + renderer tests
# (no DB access required — but we still want @django_db because the
#  builder touches the QualityAlert + AuditLog models for real counts).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDailySummaryBuilder(TestCase):
    """Unit tests for `build_daily_summary`."""

    REQUIRED_KEYS = {
        'report_date',
        'generated_at',
        'submissions_count',
        'active_trainers_count',
        'revenue_inr',
        'payout_released_inr',
        'top_3_trainers',
        'quality_alerts_open_count',
        'quality_alerts_critical_count',
        'audit_log_events_count',
        'audit_log_login_fail_count',
        'audit_log_delete_count',
        'mock_kpis',
    }

    def test_returns_all_required_keys(self):
        summary = svc.build_daily_summary()
        self.assertTrue(
            self.REQUIRED_KEYS.issubset(set(summary.keys())),
            f'Missing keys: {self.REQUIRED_KEYS - set(summary.keys())}',
        )

    def test_default_date_is_yesterday(self):
        summary = svc.build_daily_summary()
        yesterday = (timezone.now() - timedelta(days=1)).date().isoformat()
        self.assertEqual(summary['report_date'], yesterday)

    def test_explicit_date_string_parsed(self):
        summary = svc.build_daily_summary('2026-05-14')
        self.assertEqual(summary['report_date'], '2026-05-14')

    def test_explicit_date_obj_parsed(self):
        summary = svc.build_daily_summary(_date_type(2026, 5, 14))
        self.assertEqual(summary['report_date'], '2026-05-14')

    def test_top_3_trainers_capped_at_three(self):
        summary = svc.build_daily_summary()
        self.assertLessEqual(len(summary['top_3_trainers']), 3)
        for t in summary['top_3_trainers']:
            self.assertIn('id', t)
            self.assertIn('name', t)
            self.assertIn('state', t)
            self.assertIn('earnings_inr', t)
            # All amounts whole rupees — UI does no paise math.
            self.assertIsInstance(t['earnings_inr'], int)

    def test_amount_keys_are_ints(self):
        summary = svc.build_daily_summary()
        for key in (
            'submissions_count',
            'active_trainers_count',
            'revenue_inr',
            'payout_released_inr',
            'quality_alerts_open_count',
            'quality_alerts_critical_count',
            'audit_log_events_count',
            'audit_log_login_fail_count',
            'audit_log_delete_count',
        ):
            self.assertIsInstance(summary[key], int, f'{key} must be int')

    def test_mock_flag_is_true_in_phase_1(self):
        summary = svc.build_daily_summary()
        self.assertTrue(summary['mock_kpis'])

    def test_bad_date_type_raises(self):
        with self.assertRaises((TypeError, ValueError)):
            svc.build_daily_summary(12345)  # ints not supported

    def test_generated_at_is_iso_z(self):
        summary = svc.build_daily_summary()
        self.assertTrue(summary['generated_at'].endswith('Z'))
        self.assertIn('T', summary['generated_at'])


# ---------------------------------------------------------------------------
# Rendering tests
# ---------------------------------------------------------------------------


class TestEmailRendering(TestCase):
    """`render_email_html` + `render_email_text` shape contract."""

    def _summary(self, **overrides):
        # Hand-built (no DB) so this class can run without @django_db.
        base = {
            'report_date': '2026-05-14',
            'generated_at': '2026-05-15T03:00:00Z',
            'submissions_count': 1_842,
            'active_trainers_count': 87,
            'revenue_inr': 92_100,
            'payout_released_inr': 78_400,
            'top_3_trainers': [
                {'id': 5, 'name': 'Geeta P.', 'state': 'Rajasthan', 'earnings_inr': 4_350},
                {'id': 7, 'name': 'Sunil M.', 'state': 'UP', 'earnings_inr': 4_100},
                {'id': 12, 'name': 'Anil K.', 'state': 'Bihar', 'earnings_inr': 3_900},
            ],
            'quality_alerts_open_count': 4,
            'quality_alerts_critical_count': 1,
            'audit_log_events_count': 23,
            'audit_log_login_fail_count': 2,
            'audit_log_delete_count': 0,
            'mock_kpis': True,
        }
        base.update(overrides)
        return base

    def test_html_contains_brand_indigo_color(self):
        html = svc.render_email_html(self._summary())
        self.assertIn(svc.BRAND_INDIGO, html)

    def test_html_contains_saffron_or_critical_accent(self):
        html = svc.render_email_html(self._summary())
        # Saffron CTA accent OR critical red accent — both are brand-mandated
        # in the 4-tile grid.
        self.assertTrue(
            svc.BRAND_SAFFRON in html or '#DC2626' in html.upper() or '#dc2626' in html
        )

    def test_html_contains_4_kpi_tile_labels(self):
        html = svc.render_email_html(self._summary())
        for label in (
            'Submissions',
            'Revenue',
            'Active trainers',
            'Critical alerts',
        ):
            self.assertIn(label, html, f'Missing KPI tile label: {label}')

    def test_html_contains_top_3_trainer_names(self):
        html = svc.render_email_html(self._summary())
        self.assertIn('Geeta P.', html)
        self.assertIn('Sunil M.', html)
        self.assertIn('Anil K.', html)

    def test_html_contains_view_dashboard_cta(self):
        html = svc.render_email_html(self._summary())
        self.assertIn('View full dashboard', html)
        # CTA must point at the documented /admin/dashboard path.
        self.assertIn('/admin/dashboard', html)

    def test_html_contains_hindi_devanagari(self):
        """Bilingual: at least one Devanagari word in the body."""
        html = svc.render_email_html(self._summary())
        # Sample Devanagari phrases the renderer emits.
        for hi in ('कल का हाल', 'मुख्य आँकड़े', 'शीर्ष 3 प्रशिक्षक'):
            self.assertIn(hi, html, f'Missing Hindi: {hi!r}')

    def test_html_includes_report_date(self):
        html = svc.render_email_html(self._summary(report_date='2026-05-14'))
        self.assertIn('2026-05-14', html)

    def test_text_fallback_non_empty(self):
        text = svc.render_email_text(self._summary())
        self.assertGreater(len(text), 200)
        # Plain-text body also carries bilingual labels.
        self.assertIn('कल का हाल', text)
        self.assertIn('Daily Founder Report', text)

    def test_renders_with_empty_top_trainers(self):
        # Graceful degradation when nothing to show.
        html = svc.render_email_html(self._summary(top_3_trainers=[]))
        self.assertIn('No trainer activity', html)
        text = svc.render_email_text(self._summary(top_3_trainers=[]))
        self.assertIn('(no trainer activity', text)

    def test_inr_formatter_uses_lakh_grouping(self):
        self.assertEqual(svc._format_inr(100), '100')
        self.assertEqual(svc._format_inr(1234), '1,234')
        self.assertEqual(svc._format_inr(12345), '12,345')
        self.assertEqual(svc._format_inr(123456), '1,23,456')
        self.assertEqual(svc._format_inr(1234567), '12,34,567')

    def test_html_renders_when_summary_dict_has_only_some_keys(self):
        """Defensive: a partial summary still renders rather than 500ing."""
        html = svc.render_email_html(
            {'report_date': '2026-05-14', 'mock_kpis': False}
        )
        # Header text always present.
        self.assertIn('TrainPlex Studio', html)

    def test_render_email_html_rejects_non_dict(self):
        with self.assertRaises(TypeError):
            svc.render_email_html('not a dict')  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Founder-mobile guard — defensive boundary check
# ---------------------------------------------------------------------------


class TestFounderNumberGuard(TestCase):

    def test_guard_raises_on_with_cc_in_string(self):
        with self.assertRaises(ValueError):
            svc._assert_no_founder_personal_number('Call me at +91 8764 001 234')

    def test_guard_raises_on_no_cc_in_string(self):
        with self.assertRaises(ValueError):
            svc._assert_no_founder_personal_number(f'Number {_guard_no_cc()} ringing')

    def test_guard_raises_on_value_buried_in_dict(self):
        with self.assertRaises(ValueError):
            svc._assert_no_founder_personal_number(
                {'subject': 'hi', 'meta': {'phone': '+91-98765-43210'}}
            )

    def test_guard_passes_on_clean_payload(self):
        # No founder digits anywhere → should silently return None.
        result = svc._assert_no_founder_personal_number(
            {'subject': 'TrainPlex daily report', 'note': 'all good'}
        )
        self.assertIsNone(result)

    def test_rendered_html_does_not_contain_founder_number(self):
        summary = svc.build_daily_summary.__wrapped__(None) if hasattr(
            svc.build_daily_summary, '__wrapped__'
        ) else None
        # Just use the live summary since DB-touching parts return 0 in
        # the empty test DB anyway.
        summary = {
            'report_date': '2026-05-14',
            'generated_at': '2026-05-15T03:00:00Z',
            'submissions_count': 1_842,
            'active_trainers_count': 87,
            'revenue_inr': 92_100,
            'payout_released_inr': 78_400,
            'top_3_trainers': [],
            'quality_alerts_open_count': 4,
            'quality_alerts_critical_count': 1,
            'audit_log_events_count': 23,
            'audit_log_login_fail_count': 2,
            'audit_log_delete_count': 0,
            'mock_kpis': True,
        }
        html = svc.render_email_html(summary)
        text = svc.render_email_text(summary)
        _assert_no_founder_in(html, 'rendered HTML')
        _assert_no_founder_in(text, 'plain text fallback')


# ---------------------------------------------------------------------------
# Send wrapper — verifies the no-real-email contract under the dummy backend.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSendDailyReport(TestCase):

    SUMMARY = {
        'report_date': '2026-05-14',
        'generated_at': '2026-05-15T03:00:00Z',
        'submissions_count': 1,
        'active_trainers_count': 1,
        'revenue_inr': 1,
        'payout_released_inr': 1,
        'top_3_trainers': [],
        'quality_alerts_open_count': 0,
        'quality_alerts_critical_count': 0,
        'audit_log_events_count': 0,
        'audit_log_login_fail_count': 0,
        'audit_log_delete_count': 0,
        'mock_kpis': True,
    }

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend',
        TRAINPLEX_FOUNDER_EMAIL='test-founder@example.com',
    )
    def test_dummy_backend_reports_mock_mode(self):
        """Dummy backend → mode=mock, no real email leaves the box."""
        result = svc.send_daily_report(
            recipient_email=None,
            summary=self.SUMMARY,
        )
        self.assertEqual(result['recipient'], 'test-founder@example.com')
        self.assertEqual(result['mode'], 'mock')
        self.assertIn('TrainPlex daily report', result['subject'])
        # Dummy backend's send() returns 1 ("would have sent") but no SMTP
        # transit happens — `mode=mock` is the contract the caller relies on
        # to know nothing actually shipped. Don't assert `sent` either way.
        self.assertFalse(result['dry_run'])

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        TRAINPLEX_FOUNDER_EMAIL='founder@test.local',
    )
    def test_locmem_backend_records_sent(self):
        """Locmem backend stores the message in `django.core.mail.outbox`."""
        from django.core import mail as djmail
        djmail.outbox = []
        result = svc.send_daily_report(
            recipient_email=None,
            summary=self.SUMMARY,
        )
        self.assertTrue(result['sent'])
        self.assertEqual(len(djmail.outbox), 1)
        msg = djmail.outbox[0]
        self.assertEqual(msg.to, ['founder@test.local'])
        self.assertIn('TrainPlex daily report', msg.subject)
        # `attach_alternative` is recorded on `alternatives`.
        self.assertTrue(any('text/html' in alt[1] for alt in msg.alternatives))

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        TRAINPLEX_FOUNDER_EMAIL='founder@test.local',
    )
    def test_dry_run_does_not_send(self):
        """`dry_run=True` short-circuits before `EmailMultiAlternatives.send()`."""
        from django.core import mail as djmail
        djmail.outbox = []
        result = svc.send_daily_report(
            recipient_email='someone@x.com',
            summary=self.SUMMARY,
            dry_run=True,
        )
        self.assertFalse(result['sent'])
        self.assertTrue(result['dry_run'])
        self.assertEqual(len(djmail.outbox), 0)

    @override_settings(TRAINPLEX_FOUNDER_EMAIL='')
    def test_no_recipient_raises(self):
        with self.assertRaises(ValueError):
            svc.send_daily_report(recipient_email=None, summary=self.SUMMARY)

    @override_settings(TRAINPLEX_FOUNDER_EMAIL='vk.vinodparihar1@gmail.com')
    def test_recipient_override_wins_over_settings(self):
        """Explicit recipient kwarg trumps settings.TRAINPLEX_FOUNDER_EMAIL."""
        result = svc.send_daily_report(
            recipient_email='someone-else@example.com',
            summary=self.SUMMARY,
            dry_run=True,
        )
        self.assertEqual(result['recipient'], 'someone-else@example.com')


# ---------------------------------------------------------------------------
# Management command end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSendDailyReportCommand(TestCase):

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        TRAINPLEX_FOUNDER_EMAIL='founder@test.local',
    )
    def test_dry_run_succeeds_without_sending(self):
        from django.core import mail as djmail
        djmail.outbox = []
        out = StringIO()
        call_command('send_daily_report', '--dry-run', stdout=out)
        self.assertIn('dry-run', out.getvalue())
        self.assertEqual(len(djmail.outbox), 0)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        TRAINPLEX_FOUNDER_EMAIL='default@test.local',
    )
    def test_recipient_flag_overrides_default(self):
        from django.core import mail as djmail
        djmail.outbox = []
        out = StringIO()
        call_command(
            'send_daily_report',
            '--recipient', 'other@test.local',
            stdout=out,
        )
        self.assertEqual(len(djmail.outbox), 1)
        self.assertEqual(djmail.outbox[0].to, ['other@test.local'])

    @override_settings(TRAINPLEX_FOUNDER_EMAIL='founder@test.local')
    def test_bad_date_format_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command(
                'send_daily_report',
                '--date', '15-05-2026',
                '--dry-run',
            )

    @override_settings(TRAINPLEX_FOUNDER_EMAIL='')
    def test_missing_recipient_and_default_raises(self):
        with self.assertRaises(CommandError):
            call_command('send_daily_report', '--dry-run')

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        TRAINPLEX_FOUNDER_EMAIL='founder@test.local',
    )
    def test_explicit_date_propagates_to_summary(self):
        """--date flag is parsed and reflected in subject + body."""
        from django.core import mail as djmail
        djmail.outbox = []
        out = StringIO()
        call_command(
            'send_daily_report',
            '--date', '2026-05-10',
            stdout=out,
        )
        self.assertEqual(len(djmail.outbox), 1)
        msg = djmail.outbox[0]
        self.assertIn('2026-05-10', msg.subject)


# ---------------------------------------------------------------------------
# Cron-runner module entry-point smoke test
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCronRunner(TestCase):

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        TRAINPLEX_FOUNDER_EMAIL='founder@test.local',
    )
    def test_cron_run_returns_send_result(self):
        from django.core import mail as djmail
        from core.cron import daily_report as cron_mod
        djmail.outbox = []

        result = cron_mod.run()
        self.assertIn('recipient', result)
        self.assertIn('subject', result)
        self.assertEqual(len(djmail.outbox), 1)
        self.assertEqual(djmail.outbox[0].to, ['founder@test.local'])
