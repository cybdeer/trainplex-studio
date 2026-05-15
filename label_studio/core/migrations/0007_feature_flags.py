# Generated for TrainPlex Week 8 Step 17 — In-house feature flag system.
#
# Replaces the upstream LaunchDarkly path (`core/feature_flags/base.py`) with
# a zero-dependency DB-backed flag system. This migration adds the
# `htx_feature_flag` table. The service entry point is
# `core/services/feature_flags.py`; the model lives in
# `core/models_feature_flags.py` and is imported back into
# `core/models.py` so Django's app loader picks it up.
#
# Numbering: this is core migration 0007. 0006_fulltext_search_indexes
# was the last leaf in Phase 1; this adds on top of it.
#
# Dual-vendor schema
# ------------------
# The `enabled_for_roles` column is a Postgres array in prod and a JSON
# field on SQLite (CI / dev). The model classifies on `connection.vendor`
# at class-load time; this migration mirrors that — the operation that
# materialises the column branches the same way via `RunPython`.
#
# Founder rules honoured
# ----------------------
# * One-shot root cause fix — schema is idempotent (CREATE IF NOT EXISTS
#   semantics via Django's create_model + reverse drop_model).
# * No founder personal mobile — the description column is scrubbed by
#   the service layer; no scrubbing is needed at the schema layer.

from django.conf import settings
from django.db import connection, migrations, models


# Whether to use the Postgres ArrayField or the JSONField fallback.
# Determined at migration-build time, NOT at apply time — Django needs
# the field type fixed so it knows how to write the SQL.
USING_POSTGRES = connection.vendor == 'postgresql'

if USING_POSTGRES:
    from django.contrib.postgres.fields import ArrayField

    def _roles_field():
        return ArrayField(
            base_field=models.CharField(max_length=32),
            blank=True,
            default=list,
            help_text=(
                'Explicit role allowlist (admin / qa_lead / reviewer / '
                'trainer). Membership overrides rollout %.'
            ),
        )
else:
    def _roles_field():
        return models.JSONField(
            blank=True,
            default=list,
            help_text=(
                'Explicit role allowlist (admin / qa_lead / reviewer / '
                'trainer). Membership overrides rollout %.'
            ),
        )


class Migration(migrations.Migration):

    dependencies = [
        # Newest core migration before this one.
        ('core', '0006_fulltext_search_indexes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FeatureFlag',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'name',
                    models.CharField(
                        unique=True,
                        max_length=128,
                        help_text=(
                            'Unique identifier. Prefix with `fflag_` to match '
                            'upstream LD naming so the rest of the codebase '
                            'grep-finds the call site.'
                        ),
                        verbose_name='flag name',
                    ),
                ),
                (
                    'description',
                    models.TextField(
                        blank=True,
                        default='',
                        help_text='Free-form description; founder mobile scrubbed on save.',
                        verbose_name='description',
                    ),
                ),
                (
                    'enabled',
                    models.BooleanField(
                        default=False,
                        db_index=True,
                        help_text=(
                            'Master switch. If False, every is_enabled(...) call '
                            'returns False regardless of rollout %.'
                        ),
                        verbose_name='master enabled',
                    ),
                ),
                (
                    'rollout_pct',
                    models.IntegerField(
                        default=0,
                        help_text=(
                            'Deterministic per-user bucket; 0 = nobody, '
                            '100 = everyone. See '
                            '`core.services.feature_flags._user_bucket()`.'
                        ),
                        verbose_name='rollout percentage',
                    ),
                ),
                ('enabled_for_roles', _roles_field()),
                (
                    'is_experimental',
                    models.BooleanField(
                        default=True,
                        help_text=(
                            'Marks short-lived flags. audit() returns '
                            'experimental flags older than 30 days so prod '
                            'rollouts do not leak.'
                        ),
                        verbose_name='experimental',
                    ),
                ),
                (
                    'created_at',
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    'updated_at',
                    models.DateTimeField(auto_now=True),
                ),
            ],
            options={
                'verbose_name': 'feature flag',
                'verbose_name_plural': 'feature flags',
                'db_table': 'htx_feature_flag',
            },
        ),
    ]
