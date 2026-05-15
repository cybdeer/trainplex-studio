"""TrainPlex in-house feature flag model — Week 8 Step 17.

Sibling-module pattern (same as ``core/models_alerts.py`` and
``core/models_broadcast.py``): defined here, imported by ``core/models.py``
so Django's app loader registers the table under the ``core`` app.

The model is consumed by ``core/services/feature_flags.py``; views NEVER
import this module directly. The service-layer indirection is the
extension point for Phase 2 (e.g. swap to a remote store) without
touching call sites.
"""

from __future__ import annotations

from django.contrib.postgres.fields import ArrayField
from django.db import connection, models
from django.utils.translation import gettext_lazy as _


class FeatureFlag(models.Model):
    """A single feature flag definition.

    Columns
    -------
    name : str
        Unique identifier (e.g. ``fflag_payout_release_v2``). Should be
        prefixed with ``fflag_`` to match the upstream LaunchDarkly naming
        — keeps grep-ability across the codebase.
    description : text
        Free-form note. Saved through a founder-mobile scrubber (see
        :mod:`core.services.feature_flags`).
    enabled : bool
        Master switch. If False, no user gets the flag regardless of the
        rollout percentage or role allowlist.
    rollout_pct : int (0..100)
        Percentage of authenticated users (deterministically bucketed by
        ``hash(name, user_id) % 100``) for whom the flag returns True.
    enabled_for_roles : list[str]
        Explicit role allowlist (admin / qa_lead / reviewer / trainer).
        Membership in this list overrides ``rollout_pct`` (the user is
        always enabled).
    is_experimental : bool
        Marks short-lived flags. ``audit()`` returns experimental flags
        older than 30 days so production rollouts don't leak.
    """

    name = models.CharField(
        _('flag name'),
        max_length=128,
        unique=True,
        help_text=_(
            'Unique identifier. Prefix with `fflag_` to match upstream LD '
            'naming so the rest of the codebase grep-finds the call site.'
        ),
    )
    description = models.TextField(
        _('description'),
        blank=True,
        default='',
        help_text=_('Free-form description; founder mobile scrubbed on save.'),
    )
    enabled = models.BooleanField(
        _('master enabled'),
        default=False,
        db_index=True,
        help_text=_(
            'Master switch. If False, every is_enabled(...) call returns '
            'False regardless of rollout %.'
        ),
    )
    rollout_pct = models.IntegerField(
        _('rollout percentage'),
        default=0,
        help_text=_(
            'Deterministic per-user bucket; 0 = nobody, 100 = everyone. '
            'See `core.services.feature_flags._user_bucket()`.'
        ),
    )

    # JSON column for the role allowlist. Postgres gets a real array;
    # SQLite (dev/test) gets a JSONField fallback.
    if connection.vendor == 'postgresql':
        enabled_for_roles = ArrayField(
            models.CharField(max_length=32),
            blank=True,
            default=list,
            help_text=_(
                'Explicit role allowlist (admin / qa_lead / reviewer / '
                'trainer). Membership overrides rollout %.'
            ),
        )
    else:
        # SQLite dev / CI box. Django JSONField stores list[str].
        enabled_for_roles = models.JSONField(
            blank=True,
            default=list,
            help_text=_(
                'Explicit role allowlist (admin / qa_lead / reviewer / '
                'trainer). Membership overrides rollout %.'
            ),
        )

    is_experimental = models.BooleanField(
        _('experimental'),
        default=True,
        help_text=_(
            'Marks short-lived flags. audit() returns experimental flags '
            'older than 30 days so prod rollouts do not leak.'
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        db_table = 'htx_feature_flag'
        verbose_name = _('feature flag')
        verbose_name_plural = _('feature flags')

    def __str__(self) -> str:
        return f'<FeatureFlag {self.name} enabled={self.enabled} rollout={self.rollout_pct}%>'
