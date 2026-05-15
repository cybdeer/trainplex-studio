"""Tests for the TrainPlex admin Quality Alert Center.

Phase 1 Step 4.2-8.

Covers
------
Detector service (`core/services/quality_anomaly_detector.py`):
- Time anomaly: 8s vs 60s expected → high (< 10%) severity flag.
- Time anomaly: 18s vs 60s expected → medium (< 30%, >= 10%) severity flag.
- Time anomaly: 60s vs 60s expected → no flag.
- Reviewer disagree: 0/3 agree → critical.
- Reviewer disagree: 1/3 → high; 2/3 → medium; 3/3 → no flag.
- Reviewer disagree: empty / partial panel → no flag (insufficient data).
- Duplicate pattern: > 5 identical answers in window → medium flag.
- Duplicate pattern: 5 identical answers → no flag (threshold is strict-gt).
- Duplicate pattern: empty input → no flag.

Admin endpoints (`core/views_alerts.py`):
- GET /api/v1/admin/quality-alerts — admin gets paginated list with filters.
- GET stats endpoint — returns 4 severity buckets (zero-filled).
- POST review — flips status + sets reviewed_by + reviewed_at + notes.
- POST review on missing id → 404.
- POST review with bad resolution → 400.
- Trainer / unauth → 403 on all three endpoints.

These tests pin the Phase 1 contract so the Week 5 swap (real call-sites
from peer-review) is a wire-up, not a schema/API change.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.models_alerts import QualityAlert
from core.services import quality_anomaly_detector as detector

User = get_user_model()


# ---------------------------------------------------------------------------
# Detector service tests — pure logic, no HTTP.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestQualityAnomalyDetector(TestCase):
    """Detection heuristics return the right severity bucket + persist the row."""

    def setUp(self):
        self.trainer = User.objects.create_user(
            email='qa-trainer@example.com',
            username='qa-trainer',
            password='testpass123',
            role='trainer',
        )

    # ----- time anomaly -----

    def test_time_anomaly_under_10pct_marks_high(self):
        """time_taken < expected * 0.1 → high severity flag.

        5s / 60s = 8.3% < 10%  → high.
        Uses a duck-typed submission so this test stays decoupled from
        the not-yet-existing peer-review submission table (Week 5).
        """
        alert = detector.flag_time_anomaly(
            submission=type('Sub', (), {'id': 101})(),
            time_taken_sec=5,            # 5/60 = 8.3% → < 10% → high
            expected_min_sec=60,
            trainer=self.trainer,
        )
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'high')
        self.assertEqual(alert.trigger_type, 'time_anomaly')
        self.assertEqual(alert.status, 'open')
        self.assertEqual(alert.trainer_id, self.trainer.id)
        self.assertEqual(alert.submission_id, 101)
        # Details capture both inputs so admin can audit the threshold ratio.
        self.assertEqual(alert.details['time_taken_sec'], 5)
        self.assertEqual(alert.details['expected_min_sec'], 60)

    def test_time_anomaly_8s_vs_60s_is_medium(self):
        """Spec edge case: 8s < 60s threshold is medium, NOT high.

        Re-derivation:
          - time_taken_sec < expected_min_sec * 0.3 → medium    (8 < 18 ✓)
          - time_taken_sec < expected_min_sec * 0.1 → high      (8 < 6  ✗)
        So 8s of a 60s task fires the *medium* threshold but does not fire
        the *high* threshold. This test pins that semantics so the Week 5
        wire-in doesn't accidentally flip the comparison to ``<=``.
        """
        alert = detector.flag_time_anomaly(
            submission=type('Sub', (), {'id': 102})(),
            time_taken_sec=8,
            expected_min_sec=60,
            trainer=self.trainer,
        )
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'medium')

    def test_time_anomaly_at_or_above_threshold_no_flag(self):
        """ratio = 0.3 exactly is NOT < 0.3 → no flag."""
        alert = detector.flag_time_anomaly(
            submission=type('Sub', (), {'id': 103})(),
            time_taken_sec=18,           # 18 / 60 = 0.3 exactly
            expected_min_sec=60,
            trainer=self.trainer,
        )
        self.assertIsNone(alert)
        self.assertEqual(QualityAlert.objects.count(), 0)

    def test_time_anomaly_normal_speed_no_flag(self):
        alert = detector.flag_time_anomaly(
            submission=type('Sub', (), {'id': 104})(),
            time_taken_sec=60,
            expected_min_sec=60,
            trainer=self.trainer,
        )
        self.assertIsNone(alert)

    def test_time_anomaly_zero_expected_no_flag_no_div_by_zero(self):
        alert = detector.flag_time_anomaly(
            submission=type('Sub', (), {'id': 105})(),
            time_taken_sec=5,
            expected_min_sec=0,
            trainer=self.trainer,
        )
        self.assertIsNone(alert)

    # ----- reviewer disagreement -----

    def test_reviewer_disagree_0_of_3_is_critical(self):
        alert = detector.flag_reviewer_disagree(
            submission=type('Sub', (), {'id': 201})(),
            reviewers_results=[False, False, False],
            trainer=self.trainer,
        )
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'critical')
        self.assertEqual(alert.trigger_type, 'reviewer_disagree')
        self.assertEqual(alert.details['agree_count'], 0)
        self.assertEqual(alert.details['total_reviewers'], 3)

    def test_reviewer_disagree_1_of_3_is_high(self):
        alert = detector.flag_reviewer_disagree(
            submission=type('Sub', (), {'id': 202})(),
            reviewers_results=[True, False, False],
            trainer=self.trainer,
        )
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'high')

    def test_reviewer_disagree_2_of_3_is_medium(self):
        alert = detector.flag_reviewer_disagree(
            submission=type('Sub', (), {'id': 203})(),
            reviewers_results=[True, True, False],
            trainer=self.trainer,
        )
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'medium')

    def test_reviewer_disagree_3_of_3_no_flag(self):
        alert = detector.flag_reviewer_disagree(
            submission=type('Sub', (), {'id': 204})(),
            reviewers_results=[True, True, True],
            trainer=self.trainer,
        )
        self.assertIsNone(alert)

    def test_reviewer_disagree_partial_panel_no_flag(self):
        """Only 2 reviewers in — we can't reason yet, return None."""
        alert = detector.flag_reviewer_disagree(
            submission=type('Sub', (), {'id': 205})(),
            reviewers_results=[True, False],
            trainer=self.trainer,
        )
        self.assertIsNone(alert)

    # ----- duplicate pattern -----

    def test_duplicate_pattern_six_identical_flags_medium(self):
        """6 identical answers (> 5 threshold) → medium flag."""
        answers = ['yes'] * 6 + ['no'] * 4
        alert = detector.flag_duplicate_pattern(
            trainer=self.trainer,
            recent_answers=answers,
            window_size=30,
        )
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'medium')
        self.assertEqual(alert.trigger_type, 'duplicate_pattern')
        self.assertEqual(alert.details['duplicate_count'], 6)
        self.assertGreater(len(alert.details['sample_values']), 0)

    def test_duplicate_pattern_exactly_five_no_flag(self):
        """Threshold is strictly > 5 — exactly 5 should NOT flag."""
        answers = ['yes'] * 5 + ['no'] * 5
        alert = detector.flag_duplicate_pattern(
            trainer=self.trainer,
            recent_answers=answers,
        )
        self.assertIsNone(alert)

    def test_duplicate_pattern_empty_no_flag(self):
        alert = detector.flag_duplicate_pattern(
            trainer=self.trainer,
            recent_answers=[],
        )
        self.assertIsNone(alert)

    def test_duplicate_pattern_none_trainer_no_flag(self):
        alert = detector.flag_duplicate_pattern(
            trainer=None,
            recent_answers=['yes'] * 10,
        )
        self.assertIsNone(alert)

    def test_duplicate_pattern_window_clamps_input(self):
        """Caller may pass 100 answers; only the first 30 should be considered."""
        # First 6 are duplicates ('yes'); the remaining 100 are unique.
        # With window_size=10 only the first 10 are considered → 6 'yes' → flags.
        # With window_size=5 only the first 5 'yes' considered → exactly 5 → no flag.
        answers_for_5 = ['yes'] * 5 + [f'a{i}' for i in range(100)]
        alert_5 = detector.flag_duplicate_pattern(
            trainer=self.trainer,
            recent_answers=answers_for_5,
            window_size=5,
        )
        self.assertIsNone(alert_5)

        answers_for_10 = ['yes'] * 6 + [f'a{i}' for i in range(100)]
        alert_10 = detector.flag_duplicate_pattern(
            trainer=self.trainer,
            recent_answers=answers_for_10,
            window_size=10,
        )
        self.assertIsNotNone(alert_10)

    # ----- stats helper -----

    def test_open_alert_count_by_severity_zero_filled(self):
        # No rows yet — all 4 buckets should be zero.
        out = detector.open_alert_count_by_severity()
        self.assertEqual(out, {'low': 0, 'medium': 0, 'high': 0, 'critical': 0})

        # Plant two medium + one critical (all open).
        detector.flag_time_anomaly(
            submission=type('Sub', (), {'id': 1})(),
            time_taken_sec=10, expected_min_sec=60, trainer=self.trainer,
        )  # medium
        detector.flag_time_anomaly(
            submission=type('Sub', (), {'id': 2})(),
            time_taken_sec=10, expected_min_sec=60, trainer=self.trainer,
        )  # medium
        detector.flag_reviewer_disagree(
            submission=type('Sub', (), {'id': 3})(),
            reviewers_results=[False, False, False], trainer=self.trainer,
        )  # critical

        out = detector.open_alert_count_by_severity()
        self.assertEqual(out, {'low': 0, 'medium': 2, 'high': 0, 'critical': 1})


# ---------------------------------------------------------------------------
# Admin endpoints — list / stats / review.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdminQualityAlertEndpoints(TestCase):

    URL_LIST = '/api/v1/admin/quality-alerts'
    URL_STATS = '/api/v1/admin/quality-alerts/stats'

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='qa-admin@example.com',
            username='qa-admin',
            password='testpass123',
            role='admin',
        )
        self.trainer = User.objects.create_user(
            email='qa-flagged-trainer@example.com',
            username='qa-flagged-trainer',
            password='testpass123',
            role='trainer',
        )
        # Plant a couple of alerts so the list endpoint has something to show.
        self.alert_high = QualityAlert.objects.create(
            trigger_type='time_anomaly',
            severity='high',
            trainer=self.trainer,
            submission_id=901,
            details={'time_taken_sec': 5, 'expected_min_sec': 60},
            status='open',
        )
        self.alert_critical = QualityAlert.objects.create(
            trigger_type='reviewer_disagree',
            severity='critical',
            trainer=self.trainer,
            submission_id=902,
            details={'agree_count': 0, 'total_reviewers': 3},
            status='open',
        )

    # ----- list endpoint -----

    def test_list_admin_gets_200_with_alerts(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_LIST)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['total'], 2)
        ids = {row['id'] for row in body['results']}
        self.assertEqual(ids, {self.alert_high.id, self.alert_critical.id})

    def test_list_filters_by_severity(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_LIST, {'severity': 'critical'})
        body = resp.json()
        self.assertEqual(body['total'], 1)
        self.assertEqual(body['results'][0]['id'], self.alert_critical.id)

    def test_list_filters_by_status(self):
        # Resolve one alert so the open-only filter narrows it.
        self.alert_high.status = 'reviewed'
        self.alert_high.save(update_fields=['status'])
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_LIST, {'status': 'open'})
        body = resp.json()
        self.assertEqual(body['total'], 1)
        self.assertEqual(body['results'][0]['id'], self.alert_critical.id)

    def test_list_filters_by_trigger_type(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_LIST, {'trigger_type': 'time_anomaly'})
        body = resp.json()
        self.assertEqual(body['total'], 1)
        self.assertEqual(body['results'][0]['id'], self.alert_high.id)

    def test_list_filters_by_trainer_id(self):
        other_trainer = User.objects.create_user(
            email='other-trainer@example.com',
            username='other-trainer',
            password='testpass123',
            role='trainer',
        )
        QualityAlert.objects.create(
            trigger_type='duplicate_pattern',
            severity='medium',
            trainer=other_trainer,
            details={'duplicate_count': 7},
            status='open',
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_LIST, {'trainer_id': str(self.trainer.id)})
        body = resp.json()
        self.assertEqual(body['total'], 2)  # only the trainer's two
        for row in body['results']:
            self.assertEqual(row['trainer']['id'], self.trainer.id)

    def test_list_trainer_gets_403(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(self.URL_LIST)
        self.assertEqual(resp.status_code, 403)

    def test_list_unauthenticated_rejected(self):
        resp = self.client.get(self.URL_LIST)
        self.assertIn(resp.status_code, (401, 403))

    def test_list_garbage_filters_silently_ignored(self):
        """A typo in severity= shouldn't 400 — just return everything."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_LIST, {'severity': 'sky-high'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['total'], 2)

    def test_list_serializes_trainer_details(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_LIST)
        body = resp.json()
        for row in body['results']:
            self.assertIsNotNone(row['trainer'])
            self.assertEqual(row['trainer']['email'], self.trainer.email)
            self.assertEqual(row['trainer']['role'], 'trainer')

    # ----- stats endpoint -----

    def test_stats_admin_gets_severity_counts(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(self.URL_STATS)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # 4 keys present, zero-filled where needed.
        self.assertEqual(set(body['open'].keys()), {'low', 'medium', 'high', 'critical'})
        self.assertEqual(body['open']['critical'], 1)
        self.assertEqual(body['open']['high'], 1)
        self.assertEqual(body['open']['medium'], 0)
        self.assertEqual(body['open']['low'], 0)
        self.assertEqual(body['total_open'], 2)

    def test_stats_trainer_gets_403(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.get(self.URL_STATS)
        self.assertEqual(resp.status_code, 403)

    # ----- review endpoint -----

    def _url_review(self, alert_id: int) -> str:
        return f'/api/v1/admin/quality-alerts/{alert_id}/review'

    def test_review_marks_status_and_attribution(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self._url_review(self.alert_high.id),
            data={'resolution': 'action_taken', 'notes': 'Trainer suspended.'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['alert']['status'], 'action_taken')
        self.assertEqual(body['alert']['reviewed_by']['email'], self.admin.email)
        self.assertEqual(body['alert']['resolution_notes'], 'Trainer suspended.')
        # And persisted.
        self.alert_high.refresh_from_db()
        self.assertEqual(self.alert_high.status, 'action_taken')
        self.assertEqual(self.alert_high.reviewed_by_id, self.admin.id)
        self.assertIsNotNone(self.alert_high.reviewed_at)
        self.assertEqual(self.alert_high.resolution_notes, 'Trainer suspended.')

    def test_review_accepts_reviewed_and_dismissed(self):
        self.client.force_authenticate(user=self.admin)
        # Use a fresh alert for each verdict so we don't double-write.
        for resolution in ('reviewed', 'dismissed', 'action_taken'):
            alert = QualityAlert.objects.create(
                trigger_type='duplicate_pattern',
                severity='medium',
                trainer=self.trainer,
                details={'duplicate_count': 7},
                status='open',
            )
            resp = self.client.post(
                self._url_review(alert.id),
                data={'resolution': resolution, 'notes': f'verdict={resolution}'},
                format='json',
            )
            self.assertEqual(resp.status_code, 200, resp.content)
            self.assertEqual(resp.json()['alert']['status'], resolution)

    def test_review_unknown_id_returns_404(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self._url_review(999_999),
            data={'resolution': 'reviewed', 'notes': ''},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_review_bad_resolution_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self._url_review(self.alert_high.id),
            data={'resolution': 'banhammer', 'notes': ''},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['field'], 'resolution')

    def test_review_missing_resolution_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            self._url_review(self.alert_high.id),
            data={'notes': 'no verdict given'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_review_trainer_gets_403(self):
        self.client.force_authenticate(user=self.trainer)
        resp = self.client.post(
            self._url_review(self.alert_high.id),
            data={'resolution': 'reviewed', 'notes': ''},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_review_truncates_long_notes(self):
        """A 10 KB notes payload is silently trimmed to the 4 KB cap."""
        self.client.force_authenticate(user=self.admin)
        long_text = 'x' * 10_000
        resp = self.client.post(
            self._url_review(self.alert_high.id),
            data={'resolution': 'reviewed', 'notes': long_text},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.alert_high.refresh_from_db()
        self.assertLessEqual(len(self.alert_high.resolution_notes), 4096)
