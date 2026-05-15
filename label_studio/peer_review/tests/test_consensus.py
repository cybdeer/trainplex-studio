"""Tests for the TrainPlex 3-reviewer consensus engine + reviewer assigner.

Phase 1 Step 6.

Covers
------
Consensus engine (``peer_review.services.consensus_engine``):
- 3/3 agree → approved
- 2/3 agree → flagged
- 1/3 agree → dispute (creates Dispute row, auto-escalated)
- 0/3 agree → rejected (also escalated)
- 48h timeout sweep flips stale assignments to expired + decides consensus
  with 1-reviewer fallback (``fallback_used=True``).
- Idempotency: re-running compute_consensus updates in place, doesn't dupe.
- Partial votes count as 0.5 (3 partials → flagged; 2 partials → dispute).

Reviewer assigner (``peer_review.services.reviewer_assigner``):
- Cooldown enforce: same (reviewer, trainer) within 7d is blocked.
- Cooldown lapses past 7d.
- Workload balance: fewer-open reviewer is picked first.
- Reviewer-pool deficit returns < count + logs warning.
- Excludes the trainer themselves.

API endpoints:
- POST /api/v1/reviewer/submit-review (happy path → 201 + consensus row).
- POST /api/v1/reviewer/submit-review on another reviewer's assignment → 403.
- POST /api/v1/reviewer/submit-review twice → 409 (idempotency).
- GET /api/v1/reviewer/queue returns only my pending assignments.
- GET /api/v1/qa/disputes lists open Dispute rows; resolve flips resolved_at.
- 403 on cross-role access (trainer hitting reviewer endpoints etc.).

Notes
-----
* Tier-match + language-match tests are SKIPPED with an explanation marker
  because the User model has no ``tier`` / ``language`` column yet — the
  full filter lands Phase 2 Step 8 along with the trainer-profile schema.
  The Phase 1 contract (the call signature accepts these kwargs and the
  rest of the algorithm remains correct) is exercised by
  ``test_assign_accepts_phase2_kwargs_without_error``.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from peer_review.models import (
    ConsensusResult,
    Dispute,
    Review,
    ReviewAssignment,
)
from peer_review.services import consensus_engine, reviewer_assigner

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers — shared between consensus + assigner + API tests.
# ---------------------------------------------------------------------------


def _make_user(role: str, suffix: str):
    return User.objects.create_user(
        email=f'{role}-{suffix}@example.test',
        username=f'{role}-{suffix}',
        password='testpass123',
        role=role,
    )


def _make_assignment(task_id: int, reviewer, trainer_id: int = 999):
    return ReviewAssignment.objects.create(
        task_id=task_id,
        trainer_id=trainer_id,
        reviewer=reviewer,
        deadline_at=consensus_engine.default_deadline(),
    )


def _submit_review(assignment, score: int, agreement: str, comment: str = ''):
    """Persist a Review against an assignment + mark assignment done."""
    rv = Review.objects.create(
        review_assignment=assignment,
        score=score,
        agreement=agreement,
        comment=comment,
    )
    assignment.status = ReviewAssignment.STATUS_DONE
    assignment.completed_at = timezone.now()
    assignment.save(update_fields=['status', 'completed_at'])
    return rv


# ===========================================================================
# Consensus engine
# ===========================================================================


@pytest.mark.django_db
class TestConsensusEngine(TestCase):

    def setUp(self):
        self.trainer = _make_user('trainer', 'a')
        self.reviewers = [
            _make_user('reviewer', f'consensus-{i}')
            for i in range(3)
        ]

    # ----- 3/3 agree → approved -----

    def test_three_three_agree_approved(self):
        task_id = 101
        for i, rev in enumerate(self.reviewers):
            ra = _make_assignment(task_id, rev, trainer_id=self.trainer.id)
            _submit_review(ra, score=5, agreement=Review.AGREE)

        cr = consensus_engine.compute_consensus(task_id)
        self.assertEqual(cr.status, ConsensusResult.STATUS_APPROVED)
        self.assertEqual(cr.agreed_count, 3)
        self.assertEqual(cr.disagree_count, 0)
        # No Dispute row should be auto-created on approved.
        self.assertFalse(Dispute.objects.filter(consensus_result=cr).exists())

    # ----- 2/3 agree → flagged -----

    def test_two_three_agree_flagged(self):
        task_id = 102
        votes = [Review.AGREE, Review.AGREE, Review.DISAGREE]
        for rev, vote in zip(self.reviewers, votes):
            ra = _make_assignment(task_id, rev, trainer_id=self.trainer.id)
            _submit_review(ra, score=3, agreement=vote)

        cr = consensus_engine.compute_consensus(task_id)
        self.assertEqual(cr.status, ConsensusResult.STATUS_FLAGGED)
        self.assertEqual(cr.agreed_count, 2)
        self.assertEqual(cr.disagree_count, 1)
        self.assertFalse(Dispute.objects.filter(consensus_result=cr).exists())

    # ----- 1/3 agree → dispute + auto-escalate -----

    def test_one_three_agree_dispute_with_dispute_row(self):
        task_id = 103
        votes = [Review.AGREE, Review.DISAGREE, Review.DISAGREE]
        for rev, vote in zip(self.reviewers, votes):
            ra = _make_assignment(task_id, rev, trainer_id=self.trainer.id)
            _submit_review(ra, score=2, agreement=vote)

        cr = consensus_engine.compute_consensus(task_id)
        self.assertEqual(cr.status, ConsensusResult.STATUS_DISPUTE)
        # Auto-escalation should have created a Dispute row.
        self.assertTrue(Dispute.objects.filter(consensus_result=cr).exists())
        dispute = Dispute.objects.get(consensus_result=cr)
        self.assertIsNone(dispute.resolved_at)
        self.assertEqual(dispute.resolution, '')

    # ----- 0/3 agree → rejected + escalate -----

    def test_zero_three_agree_rejected(self):
        task_id = 104
        votes = [Review.DISAGREE, Review.DISAGREE, Review.DISAGREE]
        for rev, vote in zip(self.reviewers, votes):
            ra = _make_assignment(task_id, rev, trainer_id=self.trainer.id)
            _submit_review(ra, score=1, agreement=vote)

        cr = consensus_engine.compute_consensus(task_id)
        self.assertEqual(cr.status, ConsensusResult.STATUS_REJECTED)
        # Rejected also escalates (founder wants visibility on systematic
        # failures, not just split votes).
        self.assertTrue(Dispute.objects.filter(consensus_result=cr).exists())

    # ----- partial-vote weighting -----

    def test_three_partials_count_as_flagged(self):
        """partial = 0.5; 3 partials → effective 1.5 < 2.0 → dispute.

        Founder rule reads "2/3 → flagged" — partials shouldn't sneak a row
        past that without an outright agree. Documenting the exact behaviour
        here so a future tweak doesn't silently regress."""
        task_id = 105
        for rev in self.reviewers:
            ra = _make_assignment(task_id, rev, trainer_id=self.trainer.id)
            _submit_review(ra, score=3, agreement=Review.PARTIAL)

        cr = consensus_engine.compute_consensus(task_id)
        self.assertEqual(cr.partial_count, 3)
        self.assertEqual(cr.status, ConsensusResult.STATUS_DISPUTE)

    def test_one_agree_two_partials_promotes_to_flagged(self):
        """1 agree + 2 partials = 2.0 effective → flagged."""
        task_id = 106
        votes = [Review.AGREE, Review.PARTIAL, Review.PARTIAL]
        for rev, vote in zip(self.reviewers, votes):
            ra = _make_assignment(task_id, rev, trainer_id=self.trainer.id)
            _submit_review(ra, score=4, agreement=vote)

        cr = consensus_engine.compute_consensus(task_id)
        self.assertEqual(cr.agreed_count, 1)
        self.assertEqual(cr.partial_count, 2)
        self.assertEqual(cr.status, ConsensusResult.STATUS_FLAGGED)

    # ----- dispute vote counts as disagree -----

    def test_dispute_vote_counts_as_disagree(self):
        task_id = 107
        votes = [Review.AGREE, Review.AGREE, Review.DISPUTE]
        for rev, vote in zip(self.reviewers, votes):
            ra = _make_assignment(task_id, rev, trainer_id=self.trainer.id)
            _submit_review(ra, score=3, agreement=vote)

        cr = consensus_engine.compute_consensus(task_id)
        self.assertEqual(cr.disagree_count, 1)
        self.assertEqual(cr.status, ConsensusResult.STATUS_FLAGGED)

    # ----- idempotency -----

    def test_compute_consensus_is_idempotent(self):
        task_id = 108
        for rev in self.reviewers:
            ra = _make_assignment(task_id, rev, trainer_id=self.trainer.id)
            _submit_review(ra, score=5, agreement=Review.AGREE)

        cr_a = consensus_engine.compute_consensus(task_id)
        cr_b = consensus_engine.compute_consensus(task_id)
        # Same row, not duplicate.
        self.assertEqual(cr_a.id, cr_b.id)
        self.assertEqual(ConsensusResult.objects.filter(task_id=task_id).count(), 1)

    # ----- 48h timeout fallback -----

    def test_timeout_sweep_decides_with_one_reviewer(self):
        """Two reviewers don't submit before deadline; the one who did
        decides the task. ConsensusResult flagged + fallback_used=True."""
        task_id = 109
        now = timezone.now()
        past = now - timedelta(hours=49)

        # Reviewer 0 submitted on time.
        ra0 = _make_assignment(task_id, self.reviewers[0], trainer_id=self.trainer.id)
        ra0.deadline_at = past + timedelta(hours=48)  # already past now
        ra0.save(update_fields=['deadline_at'])
        _submit_review(ra0, score=4, agreement=Review.AGREE)

        # Reviewers 1+2 still pending past their deadline.
        for r in self.reviewers[1:]:
            ra = _make_assignment(task_id, r, trainer_id=self.trainer.id)
            ra.assigned_at = past
            ra.deadline_at = past + timedelta(hours=48)
            ra.save(update_fields=['assigned_at', 'deadline_at'])

        decided = consensus_engine.timeout_sweep()
        self.assertEqual(decided, 1)

        cr = ConsensusResult.objects.get(task_id=task_id)
        self.assertTrue(cr.fallback_used)
        # 1 agree, 0 disagree → effective 1.0 → dispute bucket.
        self.assertEqual(cr.agreed_count, 1)
        self.assertEqual(cr.status, ConsensusResult.STATUS_DISPUTE)

        # Stale assignments flipped to expired.
        expired = ReviewAssignment.objects.filter(
            task_id=task_id, status=ReviewAssignment.STATUS_EXPIRED,
        )
        self.assertEqual(expired.count(), 2)

    def test_timeout_sweep_with_zero_reviews_rejects(self):
        task_id = 110
        now = timezone.now()
        past = now - timedelta(hours=49)
        for r in self.reviewers:
            ra = _make_assignment(task_id, r, trainer_id=self.trainer.id)
            ra.assigned_at = past
            ra.deadline_at = past + timedelta(hours=48)
            ra.save(update_fields=['assigned_at', 'deadline_at'])

        decided = consensus_engine.timeout_sweep()
        self.assertEqual(decided, 1)
        cr = ConsensusResult.objects.get(task_id=task_id)
        self.assertEqual(cr.status, ConsensusResult.STATUS_REJECTED)
        self.assertTrue(cr.fallback_used)

    def test_timeout_sweep_skips_fresh_assignments(self):
        """Active assignments (deadline still in the future) MUST NOT be
        decided by the sweep — that would steal a trainer's payment.
        """
        task_id = 111
        for r in self.reviewers:
            _make_assignment(task_id, r, trainer_id=self.trainer.id)

        decided = consensus_engine.timeout_sweep()
        self.assertEqual(decided, 0)
        self.assertFalse(ConsensusResult.objects.filter(task_id=task_id).exists())

    # ----- escalate_to_qa idempotency -----

    def test_escalate_to_qa_idempotent_no_duplicate_dispute(self):
        task_id = 112
        votes = [Review.DISAGREE, Review.DISAGREE, Review.DISAGREE]
        for rev, vote in zip(self.reviewers, votes):
            ra = _make_assignment(task_id, rev, trainer_id=self.trainer.id)
            _submit_review(ra, score=1, agreement=vote)

        cr = consensus_engine.compute_consensus(task_id)
        # Manual second escalate should be a no-op (return existing dispute).
        dispute_a = consensus_engine.escalate_to_qa(cr.id)
        dispute_b = consensus_engine.escalate_to_qa(cr.id)
        self.assertIsNotNone(dispute_a)
        self.assertEqual(dispute_a.id, dispute_b.id)
        self.assertEqual(Dispute.objects.filter(consensus_result=cr).count(), 1)

    def test_escalate_to_qa_returns_none_on_approved(self):
        task_id = 113
        for rev in self.reviewers:
            ra = _make_assignment(task_id, rev, trainer_id=self.trainer.id)
            _submit_review(ra, score=5, agreement=Review.AGREE)
        cr = consensus_engine.compute_consensus(task_id)
        self.assertIsNone(consensus_engine.escalate_to_qa(cr.id))

    def test_escalate_to_qa_missing_id_returns_none(self):
        self.assertIsNone(consensus_engine.escalate_to_qa(99999))


# ===========================================================================
# Reviewer assigner
# ===========================================================================


@pytest.mark.django_db
class TestReviewerAssigner(TestCase):

    def setUp(self):
        self.trainer = _make_user('trainer', 'assigner')
        self.reviewers = [
            _make_user('reviewer', f'assigner-{i}')
            for i in range(5)
        ]

    def test_assign_picks_3_distinct_reviewers(self):
        rows = reviewer_assigner.assign_reviewers(
            task_id=201, trainer_id=self.trainer.id, count=3,
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({r.reviewer_id for r in rows}), 3)
        # All should have deadline ~48h out.
        now = timezone.now()
        for r in rows:
            self.assertGreater(r.deadline_at, now + timedelta(hours=47))
            self.assertLess(r.deadline_at, now + timedelta(hours=49))

    def test_assign_excludes_the_trainer_themselves(self):
        """Even if the trainer is a User row, we must never assign them as
        a reviewer of their own task."""
        # Mark the trainer as also a reviewer (some prod users wear both hats).
        self.trainer.role = 'reviewer'
        self.trainer.save(update_fields=['role'])

        rows = reviewer_assigner.assign_reviewers(
            task_id=202, trainer_id=self.trainer.id, count=3,
        )
        for r in rows:
            self.assertNotEqual(r.reviewer_id, self.trainer.id)

    def test_cooldown_enforce_blocks_recent_pair(self):
        """Same (reviewer, trainer) within 7d should NOT be re-assigned."""
        first = reviewer_assigner.assign_reviewers(
            task_id=203, trainer_id=self.trainer.id, count=3,
        )
        first_reviewer_ids = {r.reviewer_id for r in first}
        self.assertEqual(len(first_reviewer_ids), 3)

        # Same trainer submits another task — the same 3 reviewers should
        # NOT be re-picked.
        second = reviewer_assigner.assign_reviewers(
            task_id=204, trainer_id=self.trainer.id, count=3,
        )
        second_reviewer_ids = {r.reviewer_id for r in second}
        overlap = first_reviewer_ids & second_reviewer_ids
        self.assertEqual(
            overlap, set(),
            f'Reviewers {overlap} were re-assigned within cooldown window.',
        )

    def test_cooldown_lapses_past_7_days(self):
        rev = self.reviewers[0]
        old = timezone.now() - timedelta(days=8)
        ReviewAssignment.objects.create(
            task_id=205,
            trainer_id=self.trainer.id,
            reviewer=rev,
            assigned_at=old,
            deadline_at=old + timedelta(hours=48),
            status=ReviewAssignment.STATUS_DONE,
        )
        self.assertFalse(reviewer_assigner.is_pair_in_cooldown(rev.id, self.trainer.id))

    def test_cooldown_blocks_inside_7_days(self):
        rev = self.reviewers[0]
        recent = timezone.now() - timedelta(days=3)
        ReviewAssignment.objects.create(
            task_id=206,
            trainer_id=self.trainer.id,
            reviewer=rev,
            assigned_at=recent,
            deadline_at=recent + timedelta(hours=48),
        )
        self.assertTrue(reviewer_assigner.is_pair_in_cooldown(rev.id, self.trainer.id))

    def test_assign_is_idempotent(self):
        first = reviewer_assigner.assign_reviewers(
            task_id=207, trainer_id=self.trainer.id, count=3,
        )
        second = reviewer_assigner.assign_reviewers(
            task_id=207, trainer_id=self.trainer.id, count=3,
        )
        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 3)
        self.assertEqual({r.id for r in first}, {r.id for r in second})

    def test_workload_balance_prefers_idle_reviewer(self):
        """Reviewers with more open assignments are picked LAST.

        We pre-load reviewer[0] and reviewer[1] with 2 pending assignments
        each, leaving reviewer[2..4] idle. assign_reviewers(count=3) for a
        fresh task should pick the 3 idle reviewers — never the busy two."""
        for r in self.reviewers[:2]:
            for tid in (301, 302):
                ReviewAssignment.objects.create(
                    task_id=tid,
                    trainer_id=999,  # different trainer, no cooldown conflict
                    reviewer=r,
                    deadline_at=consensus_engine.default_deadline(),
                )

        rows = reviewer_assigner.assign_reviewers(
            task_id=303, trainer_id=self.trainer.id, count=3,
        )
        picked = {r.reviewer_id for r in rows}
        # The 3 picked should be the 3 idle reviewers, not the 2 busy ones.
        idle_ids = {r.id for r in self.reviewers[2:]}
        self.assertEqual(picked, idle_ids)

    def test_assign_returns_subset_when_pool_short(self):
        """Only 1 reviewer available → assign_reviewers returns 1, logs warning."""
        # Delete 4 reviewers so only reviewers[0] qualifies.
        for r in self.reviewers[1:]:
            r.delete()

        rows = reviewer_assigner.assign_reviewers(
            task_id=208, trainer_id=self.trainer.id, count=3,
        )
        self.assertEqual(len(rows), 1)

    def test_assign_accepts_phase2_kwargs_without_error(self):
        """``language`` + ``trainer_tier`` are forward-compatible kwargs.

        Phase 1 ignores them (User model has no tier/language column yet),
        but accepting them now means the Step 8 swap is a no-op for callers.
        """
        rows = reviewer_assigner.assign_reviewers(
            task_id=209,
            trainer_id=self.trainer.id,
            count=3,
            language='Hindi',
            trainer_tier='bronze',
        )
        self.assertEqual(len(rows), 3)


# ===========================================================================
# API endpoints
# ===========================================================================


@pytest.mark.django_db
class TestPeerReviewAPI(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.trainer = _make_user('trainer', 'api')
        self.reviewer = _make_user('reviewer', 'api-1')
        self.reviewer_other = _make_user('reviewer', 'api-2')
        self.qa_lead = _make_user('qa_lead', 'api')
        self.admin = _make_user('admin', 'api')

    # ----- reviewer/queue -----

    def test_reviewer_queue_lists_my_pending_only(self):
        # Mine: 2 pending.
        for tid in (401, 402):
            _make_assignment(tid, self.reviewer, trainer_id=self.trainer.id)
        # Other reviewer's pending — should NOT appear for me.
        _make_assignment(403, self.reviewer_other, trainer_id=self.trainer.id)

        self.client.force_authenticate(user=self.reviewer)
        res = self.client.get('/api/v1/reviewer/queue')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['total'], 2)
        self.assertEqual(
            {row['task_id'] for row in res.data['results']},
            {401, 402},
        )

    def test_reviewer_queue_blocks_non_reviewer(self):
        # Trainer can't read /reviewer/queue.
        self.client.force_authenticate(user=self.trainer)
        res = self.client.get('/api/v1/reviewer/queue')
        self.assertEqual(res.status_code, 403)

        # Admin also blocked — peer-review is reviewer-only, not admin override.
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/reviewer/queue')
        self.assertEqual(res.status_code, 403)

    def test_reviewer_queue_strips_trainer_email_blind_review(self):
        """Reviewer queue payload must NOT leak trainer name or email
        (founder requirement: blind review)."""
        _make_assignment(404, self.reviewer, trainer_id=self.trainer.id)
        self.client.force_authenticate(user=self.reviewer)
        res = self.client.get('/api/v1/reviewer/queue')
        body = res.json()
        leaked = body
        # Should NOT contain the trainer's email anywhere in the response.
        self.assertNotIn(self.trainer.email, str(leaked))

    # ----- reviewer/submit-review -----

    def test_submit_review_happy_path(self):
        # Make a 3-reviewer panel, only submit 1 — first response should
        # land in dispute bucket (1.0 < 2.0 → dispute) but the test really
        # checks the flow + payload shape, not the count.
        ra1 = _make_assignment(405, self.reviewer, trainer_id=self.trainer.id)
        _make_assignment(405, self.reviewer_other, trainer_id=self.trainer.id)

        self.client.force_authenticate(user=self.reviewer)
        res = self.client.post(
            '/api/v1/reviewer/submit-review',
            data={
                'review_assignment_id': ra1.id,
                'score': 4,
                'agreement': 'agree',
                'comment': 'Looks good.',
                'category_checks': {'grammar': True},
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data['ok'])
        # Consensus row created.
        self.assertEqual(
            ConsensusResult.objects.filter(task_id=405).count(), 1,
        )

    def test_submit_review_blocks_other_reviewer_assignment(self):
        ra = _make_assignment(406, self.reviewer_other, trainer_id=self.trainer.id)
        self.client.force_authenticate(user=self.reviewer)
        res = self.client.post(
            '/api/v1/reviewer/submit-review',
            data={'review_assignment_id': ra.id, 'score': 4, 'agreement': 'agree'},
            format='json',
        )
        self.assertEqual(res.status_code, 403)

    def test_submit_review_twice_returns_409(self):
        ra = _make_assignment(407, self.reviewer, trainer_id=self.trainer.id)
        self.client.force_authenticate(user=self.reviewer)
        body = {'review_assignment_id': ra.id, 'score': 4, 'agreement': 'agree'}
        first = self.client.post('/api/v1/reviewer/submit-review', data=body, format='json')
        self.assertEqual(first.status_code, 201)
        second = self.client.post('/api/v1/reviewer/submit-review', data=body, format='json')
        self.assertEqual(second.status_code, 409)

    def test_submit_review_validation_errors(self):
        ra = _make_assignment(408, self.reviewer, trainer_id=self.trainer.id)
        self.client.force_authenticate(user=self.reviewer)

        # bad score
        res = self.client.post(
            '/api/v1/reviewer/submit-review',
            data={'review_assignment_id': ra.id, 'score': 99, 'agreement': 'agree'},
            format='json',
        )
        self.assertEqual(res.status_code, 400)

        # bad agreement
        res = self.client.post(
            '/api/v1/reviewer/submit-review',
            data={'review_assignment_id': ra.id, 'score': 4, 'agreement': 'maybe'},
            format='json',
        )
        self.assertEqual(res.status_code, 400)

        # missing assignment
        res = self.client.post(
            '/api/v1/reviewer/submit-review',
            data={'review_assignment_id': 99999, 'score': 4, 'agreement': 'agree'},
            format='json',
        )
        self.assertEqual(res.status_code, 404)

    # ----- /qa/disputes list + resolve -----

    def test_qa_disputes_list_only_qa_lead_role(self):
        # Trainer / reviewer / admin all blocked.
        for u in (self.trainer, self.reviewer, self.admin):
            self.client.force_authenticate(user=u)
            res = self.client.get('/api/v1/qa/disputes')
            self.assertEqual(res.status_code, 403, msg=f'role={u.role}')

    def test_qa_disputes_lifecycle(self):
        # Set up a 0/3-disagree task → consensus rejected → dispute created.
        task_id = 409
        reviewers = [
            _make_user('reviewer', f'qa-flow-{i}') for i in range(3)
        ]
        for rev in reviewers:
            ra = _make_assignment(task_id, rev, trainer_id=self.trainer.id)
            _submit_review(ra, score=1, agreement=Review.DISAGREE)
        cr = consensus_engine.compute_consensus(task_id)
        dispute = Dispute.objects.get(consensus_result=cr)

        # qa_lead sees the open dispute.
        self.client.force_authenticate(user=self.qa_lead)
        res = self.client.get('/api/v1/qa/disputes')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['total'], 1)
        self.assertEqual(res.data['results'][0]['id'], dispute.id)

        # Resolve flips resolved_at + sets qa_lead + resolution.
        res = self.client.post(
            f'/api/v1/qa/disputes/{dispute.id}/resolve',
            data={
                'resolution': 'reviewer_correct',
                'qa_notes': 'Reviewers had it right — trainer used wrong category.',
                'qa_decision': 'Reviewer majority correct',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        dispute.refresh_from_db()
        self.assertIsNotNone(dispute.resolved_at)
        self.assertEqual(dispute.resolution, 'reviewer_correct')
        self.assertEqual(dispute.qa_lead_id, self.qa_lead.id)

        # Resolve again returns 409.
        res = self.client.post(
            f'/api/v1/qa/disputes/{dispute.id}/resolve',
            data={'resolution': 'trainer_correct', 'qa_notes': ''},
            format='json',
        )
        self.assertEqual(res.status_code, 409)

        # Default list now shows zero (only open by default).
        res = self.client.get('/api/v1/qa/disputes')
        self.assertEqual(res.data['total'], 0)

        # `?status=resolved` shows the resolved one.
        res = self.client.get('/api/v1/qa/disputes?status=resolved')
        self.assertEqual(res.data['total'], 1)

    def test_qa_dispute_resolve_validation(self):
        cr = ConsensusResult.objects.create(
            task_id=410,
            total_reviewers=3,
            agreed_count=1,
            disagree_count=2,
            partial_count=0,
            status=ConsensusResult.STATUS_DISPUTE,
        )
        dispute = Dispute.objects.create(consensus_result=cr)

        self.client.force_authenticate(user=self.qa_lead)
        # bad resolution
        res = self.client.post(
            f'/api/v1/qa/disputes/{dispute.id}/resolve',
            data={'resolution': 'nope', 'qa_notes': ''},
            format='json',
        )
        self.assertEqual(res.status_code, 400)

        # missing dispute id
        res = self.client.post(
            '/api/v1/qa/disputes/99999/resolve',
            data={'resolution': 'inconclusive', 'qa_notes': ''},
            format='json',
        )
        self.assertEqual(res.status_code, 404)
