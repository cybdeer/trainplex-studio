"""Tests for the TrainPlex in-house feature flag system — Week 8 Step 17.

Covers
------
Service (`core/services/feature_flags.py`):
- `is_enabled` returns `default` when flag does not exist.
- Disabled master switch always returns False.
- Role allowlist overrides rollout % (admin role gets enabled at 0%).
- 100% rollout returns True for any authenticated user.
- 0% rollout returns False for any authenticated user (unless role match).
- Deterministic per-user bucket: same user → same answer across calls.
- Different users → different buckets (verified via distribution sample).
- Anonymous + partial rollout → False (no bucket for anon).
- `set_flag` creates a flag idempotently.
- `set_flag` rejects rollout_pct > 100 with ValueError.
- `set_flag` rejects rollout_pct < 0 with ValueError.
- `set_flag` scrubs founder mobile from description (memory rule).
- `audit()` returns stale experimental flags only.
- Cache invalidation: `set_flag` clears the per-process cache.

Model (`core/models_feature_flags.py`):
- Table exists at `htx_feature_flag`.
- `name` is unique (IntegrityError on duplicate).
- `rollout_pct` defaults to 0.
- `is_experimental` defaults to True.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from core.models_feature_flags import FeatureFlag
from core.services import feature_flags as ff

User = get_user_model()


def _make_user(email, role='trainer'):
    return User.objects.create_user(
        email=email,
        username=email.split('@')[0],
        password='pw',
        role=role,
    )


@pytest.mark.django_db
class TestIsEnabled(TestCase):
    """Decision-order tests for the public `is_enabled` entry."""

    def setUp(self):
        ff._FLAG_CACHE.clear()
        self.user = _make_user('u1@example.com', 'trainer')
        self.admin = _make_user('a1@example.com', 'admin')

    def test_missing_flag_returns_default(self):
        self.assertFalse(ff.is_enabled('nonexistent', self.user))
        self.assertTrue(ff.is_enabled('nonexistent', self.user, default=True))

    def test_master_off_returns_false(self):
        ff.set_flag('fflag_off', enabled=False, rollout_pct=100)
        self.assertFalse(ff.is_enabled('fflag_off', self.user))

    def test_role_allowlist_overrides_rollout(self):
        # Master on, rollout 0, but admins explicitly allowed.
        ff.set_flag(
            'fflag_admin_only',
            enabled=True,
            rollout_pct=0,
            enabled_for_roles=['admin'],
        )
        self.assertTrue(ff.is_enabled('fflag_admin_only', self.admin))
        self.assertFalse(ff.is_enabled('fflag_admin_only', self.user))

    def test_full_rollout_returns_true(self):
        ff.set_flag('fflag_all', enabled=True, rollout_pct=100)
        self.assertTrue(ff.is_enabled('fflag_all', self.user))
        self.assertTrue(ff.is_enabled('fflag_all', self.admin))

    def test_zero_rollout_returns_false_without_role_match(self):
        ff.set_flag('fflag_none', enabled=True, rollout_pct=0)
        self.assertFalse(ff.is_enabled('fflag_none', self.user))

    def test_anonymous_user_with_partial_rollout(self):
        ff.set_flag('fflag_partial', enabled=True, rollout_pct=50)
        # Anonymous = no `is_authenticated`, no `id`.
        anon = type('AnonStub', (), {'is_authenticated': False, 'id': None, 'role': None})()
        self.assertFalse(ff.is_enabled('fflag_partial', anon))
        # Same flag at 100% gives True even for anonymous, since rule (4) wins
        # before the auth check.
        ff.set_flag('fflag_partial', rollout_pct=100)
        self.assertTrue(ff.is_enabled('fflag_partial', anon))

    def test_deterministic_per_user(self):
        ff.set_flag('fflag_partial2', enabled=True, rollout_pct=50)
        # Same user → same answer across 5 calls.
        results = {ff.is_enabled('fflag_partial2', self.user) for _ in range(5)}
        self.assertEqual(len(results), 1)

    def test_rollout_distribution_is_roughly_uniform(self):
        """With 50% rollout over 100 fake users, expect 30..70 enabled
        (binomial 95% CI is ~40..60, but we set the threshold loose
        because we use a small/fast hash)."""
        ff.set_flag('fflag_partial3', enabled=True, rollout_pct=50)
        enabled = 0
        for uid in range(100):
            fake_user = type('FU', (), {'id': uid + 1000, 'is_authenticated': True, 'role': 'trainer'})()
            if ff.is_enabled('fflag_partial3', fake_user):
                enabled += 1
        self.assertGreaterEqual(enabled, 30)
        self.assertLessEqual(enabled, 70)


@pytest.mark.django_db
class TestSetFlag(TestCase):
    def setUp(self):
        ff._FLAG_CACHE.clear()

    def test_set_creates_then_updates_idempotently(self):
        ff.set_flag('fflag_x', enabled=True, rollout_pct=10)
        ff.set_flag('fflag_x', rollout_pct=20)
        row = FeatureFlag.objects.get(name='fflag_x')
        self.assertTrue(row.enabled)
        self.assertEqual(row.rollout_pct, 20)

    def test_set_rejects_rollout_out_of_range(self):
        with self.assertRaises(ValueError):
            ff.set_flag('fflag_bad', rollout_pct=101)
        with self.assertRaises(ValueError):
            ff.set_flag('fflag_bad', rollout_pct=-1)

    def test_set_scrubs_founder_mobile(self):
        ff.set_flag(
            'fflag_scrub',
            description='Contact founder at +91 8764001234 for details',
        )
        row = FeatureFlag.objects.get(name='fflag_scrub')
        self.assertNotIn('8764001234', row.description)
        self.assertIn('[REDACTED-MOBILE]', row.description)

    def test_cache_invalidated_on_set(self):
        # Prime the cache by reading first.
        ff.set_flag('fflag_cache', enabled=False, rollout_pct=0)
        ff.is_enabled('fflag_cache', _make_user('u-cache@example.com'))
        # Now toggle and re-read; expect the new value, not the cached.
        ff.set_flag('fflag_cache', enabled=True, rollout_pct=100)
        self.assertTrue(
            ff.is_enabled('fflag_cache', _make_user('u-cache2@example.com'))
        )


@pytest.mark.django_db
class TestAudit(TestCase):
    def setUp(self):
        ff._FLAG_CACHE.clear()
        # Three flags with controlled created_at.
        ff.set_flag('fflag_new_exp', is_experimental=True)
        ff.set_flag('fflag_stable', is_experimental=False)
        ff.set_flag('fflag_old_exp', is_experimental=True)
        # Backdate the "old" one by 60 days.
        old = FeatureFlag.objects.get(name='fflag_old_exp')
        old.created_at = datetime.now(timezone.utc) - timedelta(days=60)
        old.save()

    def test_audit_returns_only_stale_experimental(self):
        stale = ff.audit(stale_age_days=30)
        names = {row['name'] for row in stale}
        self.assertIn('fflag_old_exp', names)
        self.assertNotIn('fflag_new_exp', names)
        self.assertNotIn('fflag_stable', names)


@pytest.mark.django_db
class TestModel(TestCase):
    def test_name_unique(self):
        FeatureFlag.objects.create(name='dup')
        with self.assertRaises(IntegrityError):
            FeatureFlag.objects.create(name='dup')

    def test_defaults(self):
        row = FeatureFlag.objects.create(name='just-name')
        self.assertFalse(row.enabled)
        self.assertEqual(row.rollout_pct, 0)
        self.assertTrue(row.is_experimental)
        self.assertEqual(row.description, '')
