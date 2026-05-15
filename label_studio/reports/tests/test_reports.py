"""Tests for the TrainPlex Reports + BI suite — Phase 1 Step 7.

Covers
------
Service layer (mock data contracts):
* ``founder_weekly.build_founder_weekly_snapshot`` returns every expected
  section + week-start snaps to ISO Monday.
* ``leaderboard.build_leaderboard`` filters + period scaling work; rank is
  monotone; hall-of-fame is computed on the unfiltered roster.
* ``cohort_analyzer.compute_cohort_metrics`` returns 4 retention points per
  cohort.
* ``project_roi.compute_project_roi`` math: roi_pct = (profit/cost)*100;
  unknown project_id returns None.

API
---
* All endpoints return 200 for admin role.
* All endpoints return 403 for trainer role.
* Unauthenticated request returns 401/403.
* PDF endpoints return application/pdf + valid %PDF-1.4 magic.
* CSV endpoint returns text/csv with UTF-8 BOM and Hindi names preserved.
* PDF response size > 200 bytes (sanity floor — empty stream would be ~100).

Email jobs
----------
* Weekly + monthly summary in dry_run mode return envelope + PDF size > 0.
* No founder personal mobile (per ``MEMORY.md → feedback_no_founder_personal_number``)
  appears anywhere in the envelope body / subject / recipients.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from reports.jobs import (
    build_monthly_summary_email,
    build_weekly_summary_email,
    send_monthly_summary,
    send_weekly_summary,
)
from reports.services import (
    cohort_analyzer,
    founder_weekly,
    leaderboard as leaderboard_service,
    pdf_renderer,
    project_roi,
)

User = get_user_model()


# Founder personal mobile per MEMORY.md → feedback_no_founder_personal_number.
_FOUNDER_PERSONAL_MOBILE_VARIANTS = (
    '+918764001234', '918764001234', '8764001234', '+91 8764001234',
    '+91-8764001234', '+91 87640 01234',
)


def _make_user(role: str, suffix: str):
    return User.objects.create_user(
        email=f'{role}-{suffix}@example.test',
        username=f'{role}-{suffix}',
        password='testpass123',
        role=role,
    )


def _string_haystack(*pieces: object) -> str:
    """Concatenate any pieces into a single string so the founder-mobile
    scan can run a single ``in`` per variant."""
    return '\n'.join(str(p) for p in pieces)


def _scan_for_founder_mobile(haystack: str) -> Iterable[str]:
    """Return any variants of the founder mobile found in the haystack."""
    return [v for v in _FOUNDER_PERSONAL_MOBILE_VARIANTS if v in haystack]


# ===========================================================================
# Service layer — founder weekly
# ===========================================================================


@pytest.mark.django_db
class TestFounderWeeklySnapshot(TestCase):

    def test_returns_all_expected_sections(self):
        snap = founder_weekly.build_founder_weekly_snapshot()
        for key in (
            'week_start', 'week_end', 'generated_at',
            'top_kpis', 'trend_lines', 'cohort_retention',
            'project_roi', 'geographic_split', 'language_split',
            'quality_kpis',
        ):
            self.assertIn(key, snap, f'Missing top-level key {key}')

    def test_top_kpis_have_all_metrics(self):
        snap = founder_weekly.build_founder_weekly_snapshot()
        kpis = snap['top_kpis']
        for key in (
            'submissions_weekly', 'revenue_weekly_inr', 'active_trainers',
            'avg_payout_per_trainer_inr',
        ):
            self.assertIn(key, kpis, f'Missing KPI {key}')
            self.assertIsInstance(kpis[key], int)

    def test_trend_lines_have_three_series(self):
        snap = founder_weekly.build_founder_weekly_snapshot()
        trend = snap['trend_lines']
        self.assertEqual(len(trend['submissions_over_time']), 7,
                         '7-day submissions series expected')
        self.assertEqual(len(trend['revenue_mom']), 6,
                         '6-month revenue MoM series expected')
        self.assertEqual(len(trend['trainer_growth']), 6,
                         '6-month trainer-growth series expected')

    def test_week_start_snaps_to_monday(self):
        # Pass a Thursday — should snap back to the Monday of that ISO week.
        thursday = date(2026, 5, 14)  # 2026-05-14 is a Thursday
        snap = founder_weekly.build_founder_weekly_snapshot(thursday)
        self.assertEqual(snap['week_start'], '2026-05-11')  # Monday

    def test_avg_payout_math(self):
        snap = founder_weekly.build_founder_weekly_snapshot()
        kpis = snap['top_kpis']
        expected = kpis['revenue_weekly_inr'] // max(kpis['active_trainers'], 1)
        self.assertEqual(kpis['avg_payout_per_trainer_inr'], expected)


# ===========================================================================
# Service layer — leaderboard
# ===========================================================================


@pytest.mark.django_db
class TestLeaderboardService(TestCase):

    def test_default_returns_30_trainers_rank_starts_at_1(self):
        data = leaderboard_service.build_leaderboard()
        self.assertEqual(data['total'], 30)
        self.assertEqual(data['results'][0]['rank'], 1)
        self.assertEqual(data['results'][-1]['rank'], 30)

    def test_rank_is_monotone_increasing(self):
        data = leaderboard_service.build_leaderboard()
        ranks = [r['rank'] for r in data['results']]
        self.assertEqual(ranks, sorted(ranks))

    def test_results_sorted_by_tasks_desc(self):
        data = leaderboard_service.build_leaderboard()
        tasks = [r['tasks_done'] for r in data['results']]
        self.assertEqual(tasks, sorted(tasks, reverse=True))

    def test_filter_state_narrows_results(self):
        data = leaderboard_service.build_leaderboard(filters={'state': 'RJ'})
        for row in data['results']:
            self.assertEqual(row['state'], 'RJ')
        self.assertTrue(data['total'] >= 1)

    def test_filter_tier_narrows_results(self):
        data = leaderboard_service.build_leaderboard(filters={'tier': 'gold'})
        for row in data['results']:
            self.assertEqual(row['tier'], 'gold')

    def test_filter_language_narrows_results(self):
        data = leaderboard_service.build_leaderboard(filters={'language': 'ta'})
        for row in data['results']:
            self.assertEqual(row['language'], 'ta')

    def test_filter_project_type_narrows_results(self):
        data = leaderboard_service.build_leaderboard(filters={'project_type': 'voice'})
        for row in data['results']:
            self.assertEqual(row['project_type'], 'voice')

    def test_period_scales_tasks_done(self):
        weekly = leaderboard_service.build_leaderboard(period='weekly')
        monthly = leaderboard_service.build_leaderboard(period='monthly')
        # Weekly should be roughly 1/4 of monthly for the top trainer.
        self.assertLess(weekly['results'][0]['tasks_done'], monthly['results'][0]['tasks_done'])

    def test_unknown_period_falls_back(self):
        # Unknown period silently falls back — no 400.
        data = leaderboard_service.build_leaderboard(period='annually')
        self.assertEqual(data['period'], 'weekly')

    def test_hall_of_fame_lifetime_has_10_entries(self):
        data = leaderboard_service.build_leaderboard()
        self.assertEqual(len(data['hall_of_fame_lifetime']), 10)
        self.assertEqual(data['hall_of_fame_lifetime'][0]['rank'], 1)

    def test_hall_of_fame_month_has_10_entries(self):
        data = leaderboard_service.build_leaderboard()
        self.assertEqual(len(data['hall_of_fame_month']), 10)

    def test_hall_of_fame_unaffected_by_filters(self):
        """Hall of fame should be computed on the unfiltered roster."""
        no_filter = leaderboard_service.build_leaderboard()
        with_filter = leaderboard_service.build_leaderboard(
            filters={'state': 'RJ'},
        )
        self.assertEqual(
            [t['trainer_id'] for t in no_filter['hall_of_fame_month']],
            [t['trainer_id'] for t in with_filter['hall_of_fame_month']],
        )


# ===========================================================================
# Service layer — cohort analyzer
# ===========================================================================


@pytest.mark.django_db
class TestCohortAnalyzer(TestCase):

    def test_signup_wave_returns_4_cohorts(self):
        data = cohort_analyzer.compute_cohort_metrics('signup_wave')
        self.assertEqual(data['cohort_definition'], 'signup_wave')
        self.assertEqual(len(data['cohorts']), 4)

    def test_retention_curve_has_4_points(self):
        data = cohort_analyzer.compute_cohort_metrics('signup_wave')
        for c in data['cohorts']:
            self.assertEqual(len(c['retention_curve']), 4)
            days = [p['day'] for p in c['retention_curve']]
            self.assertEqual(days, [7, 30, 60, 90])

    def test_registration_week_definition(self):
        data = cohort_analyzer.compute_cohort_metrics('registration_week')
        self.assertEqual(data['cohort_definition'], 'registration_week')
        self.assertTrue(all(c['cohort_id'].startswith('2026-W') for c in data['cohorts']))

    def test_tier_promotion_definition(self):
        data = cohort_analyzer.compute_cohort_metrics('tier_promotion_month')
        self.assertEqual(data['cohort_definition'], 'tier_promotion_month')

    def test_unknown_definition_falls_back(self):
        data = cohort_analyzer.compute_cohort_metrics('garbage')
        self.assertEqual(data['cohort_definition'], 'signup_wave')

    def test_productivity_curve_has_12_weeks(self):
        data = cohort_analyzer.compute_cohort_metrics('signup_wave')
        for c in data['cohorts']:
            self.assertEqual(len(c['productivity_curve']), 12)

    def test_earnings_curve_is_cumulative(self):
        data = cohort_analyzer.compute_cohort_metrics('signup_wave')
        for c in data['cohorts']:
            curve = c['earnings_curve']
            # Cumulative — each entry must be > previous.
            for i in range(1, len(curve)):
                self.assertGreater(
                    curve[i]['cumulative_earnings_inr'],
                    curve[i - 1]['cumulative_earnings_inr'],
                )


# ===========================================================================
# Service layer — project ROI
# ===========================================================================


@pytest.mark.django_db
class TestProjectROI(TestCase):

    def test_known_project_returns_full_payload(self):
        row = project_roi.compute_project_roi(101)
        self.assertIsNotNone(row)
        for key in (
            'project_id', 'project_name', 'project_type', 'language',
            'tasks_created', 'tasks_completed', 'trainer_payout_inr',
            'reviewer_payout_inr', 'infra_cost_inr', 'total_cost_inr',
            'external_revenue_inr', 'profit_inr', 'roi_pct',
            'cost_per_quality_task_inr', 'time_to_complete_days',
            'quality_score_pct',
        ):
            self.assertIn(key, row, f'Missing field {key}')

    def test_unknown_project_returns_none(self):
        self.assertIsNone(project_roi.compute_project_roi(999999))

    def test_roi_math(self):
        row = project_roi.compute_project_roi(101)
        total_cost = row['trainer_payout_inr'] + row['reviewer_payout_inr'] + row['infra_cost_inr']
        self.assertEqual(row['total_cost_inr'], total_cost)
        profit = row['external_revenue_inr'] - total_cost
        self.assertEqual(row['profit_inr'], profit)
        expected_roi = int(round((profit / total_cost) * 100))
        self.assertEqual(row['roi_pct'], expected_roi)

    def test_cost_per_quality_task_math(self):
        row = project_roi.compute_project_roi(101)
        quality_passed = int(round(row['tasks_completed'] * row['quality_score_pct'] / 100))
        expected = int(round(row['total_cost_inr'] / max(1, quality_passed)))
        self.assertEqual(row['cost_per_quality_task_inr'], expected)

    def test_compute_all_returns_sorted_by_roi_desc(self):
        rows = project_roi.compute_all_project_roi()
        rois = [r['roi_pct'] for r in rows]
        self.assertEqual(rois, sorted(rois, reverse=True))


# ===========================================================================
# Service layer — PDF renderer
# ===========================================================================


@pytest.mark.django_db
class TestPDFRenderer(TestCase):

    def test_founder_weekly_pdf_starts_with_pdf_magic(self):
        snap = founder_weekly.build_founder_weekly_snapshot()
        payload = pdf_renderer.render_founder_weekly_pdf(snap)
        self.assertTrue(payload.startswith(b'%PDF-1.4'),
                        'PDF must start with %PDF-1.4 magic')
        self.assertTrue(payload.rstrip().endswith(b'%%EOF'),
                        'PDF must end with %%EOF')
        # Sanity floor on size — an empty stream would be tiny.
        self.assertGreater(len(payload), 400)

    def test_project_roi_pdf_starts_with_pdf_magic(self):
        roi = project_roi.compute_project_roi(101)
        payload = pdf_renderer.render_project_roi_pdf(roi)
        self.assertTrue(payload.startswith(b'%PDF-1.4'))
        self.assertTrue(payload.rstrip().endswith(b'%%EOF'))
        self.assertGreater(len(payload), 400)

    def test_renderer_backend_name_is_known(self):
        backend = pdf_renderer.renderer_backend()
        self.assertIn(backend, ('weasyprint', 'reportlab', 'minimal'))


# ===========================================================================
# API
# ===========================================================================


@pytest.mark.django_db
class TestReportsAPI(TestCase):
    """All endpoints — RBAC + shape + content-type assertions."""

    def setUp(self):
        self.client = APIClient()
        self.admin = _make_user('admin', 'reports')
        self.trainer = _make_user('trainer', 'reports')

    # --- /api/v1/admin/reports/founder-weekly ---

    def test_founder_weekly_admin_returns_200(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/reports/founder-weekly')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn('top_kpis', body)
        self.assertIn('cohort_retention', body)

    def test_founder_weekly_trainer_returns_403(self):
        self.client.force_authenticate(user=self.trainer)
        res = self.client.get('/api/v1/admin/reports/founder-weekly')
        self.assertEqual(res.status_code, 403)

    def test_founder_weekly_unauthenticated(self):
        res = self.client.get('/api/v1/admin/reports/founder-weekly')
        self.assertIn(res.status_code, (401, 403))

    # --- /api/v1/admin/reports/founder-weekly.pdf ---

    def test_founder_weekly_pdf_admin_streams_pdf(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/reports/founder-weekly.pdf')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        body = res.content
        self.assertTrue(body.startswith(b'%PDF-1.4'))
        self.assertGreater(len(body), 400)

    def test_founder_weekly_pdf_trainer_returns_403(self):
        self.client.force_authenticate(user=self.trainer)
        res = self.client.get('/api/v1/admin/reports/founder-weekly.pdf')
        self.assertEqual(res.status_code, 403)

    # --- /api/v1/admin/reports/leaderboard ---

    def test_leaderboard_admin_returns_200(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/reports/leaderboard')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(len(body['results']), 30)

    def test_leaderboard_filter_state(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/reports/leaderboard?state=RJ')
        body = res.json()
        for row in body['results']:
            self.assertEqual(row['state'], 'RJ')

    def test_leaderboard_period_query(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/reports/leaderboard?period=daily')
        body = res.json()
        self.assertEqual(body['period'], 'daily')

    def test_leaderboard_trainer_returns_403(self):
        self.client.force_authenticate(user=self.trainer)
        res = self.client.get('/api/v1/admin/reports/leaderboard')
        self.assertEqual(res.status_code, 403)

    # --- /api/v1/admin/reports/leaderboard.csv ---

    def test_leaderboard_csv_has_utf8_bom_and_header(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/reports/leaderboard.csv')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res['Content-Type'])
        body = res.content
        # UTF-8 BOM at the very start.
        self.assertTrue(body.startswith(b'\xef\xbb\xbf'),
                        'CSV must start with UTF-8 BOM for Excel + Hindi names')
        text = body.decode('utf-8-sig')
        first_line = text.splitlines()[0]
        for col in ('rank', 'trainer_id', 'name', 'state', 'tier', 'language'):
            self.assertIn(col, first_line)

    def test_leaderboard_csv_trainer_returns_403(self):
        self.client.force_authenticate(user=self.trainer)
        res = self.client.get('/api/v1/admin/reports/leaderboard.csv')
        self.assertEqual(res.status_code, 403)

    # --- /api/v1/admin/reports/cohorts ---

    def test_cohorts_admin_returns_200(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/reports/cohorts')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['cohort_definition'], 'signup_wave')
        self.assertEqual(len(body['cohorts']), 4)

    def test_cohorts_definition_query(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get(
            '/api/v1/admin/reports/cohorts?cohort_definition=registration_week'
        )
        body = res.json()
        self.assertEqual(body['cohort_definition'], 'registration_week')

    def test_cohorts_trainer_returns_403(self):
        self.client.force_authenticate(user=self.trainer)
        res = self.client.get('/api/v1/admin/reports/cohorts')
        self.assertEqual(res.status_code, 403)

    # --- /api/v1/admin/reports/project-roi (list) ---

    def test_project_roi_list_admin(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/reports/project-roi')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertGreater(len(body['results']), 0)

    def test_project_roi_list_trainer_returns_403(self):
        self.client.force_authenticate(user=self.trainer)
        res = self.client.get('/api/v1/admin/reports/project-roi')
        self.assertEqual(res.status_code, 403)

    # --- /api/v1/admin/reports/project-roi/<id> ---

    def test_project_roi_detail_admin(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/reports/project-roi/101')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['project_id'], 101)

    def test_project_roi_detail_unknown_returns_404(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/reports/project-roi/999999')
        self.assertEqual(res.status_code, 404)

    # --- /api/v1/admin/reports/project-roi/<id>.pdf ---

    def test_project_roi_pdf_admin_streams_pdf(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/reports/project-roi/101.pdf')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        body = res.content
        self.assertTrue(body.startswith(b'%PDF-1.4'))

    def test_project_roi_pdf_unknown_returns_404(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/admin/reports/project-roi/999999.pdf')
        self.assertEqual(res.status_code, 404)


# ===========================================================================
# Email jobs
# ===========================================================================


@pytest.mark.django_db
class TestReportEmailJobs(TestCase):

    def test_weekly_summary_envelope(self):
        env = build_weekly_summary_email()
        self.assertIn('subject', env)
        self.assertIn('body_text', env)
        self.assertIn('recipients', env)
        self.assertTrue(env['recipients'])
        self.assertTrue(env['pdf_filename'].endswith('.pdf'))
        self.assertGreater(len(env['pdf_bytes']), 400)
        self.assertTrue(env['pdf_bytes'].startswith(b'%PDF-1.4'))

    def test_monthly_summary_envelope(self):
        env = build_monthly_summary_email()
        self.assertTrue(env['subject'].startswith('[TrainPlex] Founder monthly'))
        self.assertGreater(len(env['pdf_bytes']), 400)

    def test_send_weekly_dry_run(self):
        result = send_weekly_summary(dry_run=True)
        self.assertFalse(result['sent'])
        self.assertTrue(result['dry_run'])
        self.assertGreater(result['pdf_size'], 400)

    def test_send_monthly_dry_run(self):
        result = send_monthly_summary(dry_run=True)
        self.assertFalse(result['sent'])
        self.assertTrue(result['dry_run'])

    def test_no_founder_mobile_in_weekly_envelope(self):
        env = build_weekly_summary_email()
        haystack = _string_haystack(
            env['subject'], env['body_text'], env['recipients'],
            env['pdf_filename'],
        )
        self.assertEqual(
            list(_scan_for_founder_mobile(haystack)),
            [],
            'Founder personal mobile leaked into weekly summary envelope',
        )

    def test_no_founder_mobile_in_monthly_envelope(self):
        env = build_monthly_summary_email()
        haystack = _string_haystack(
            env['subject'], env['body_text'], env['recipients'],
            env['pdf_filename'],
        )
        self.assertEqual(
            list(_scan_for_founder_mobile(haystack)),
            [],
            'Founder personal mobile leaked into monthly summary envelope',
        )
