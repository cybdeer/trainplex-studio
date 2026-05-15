# Generated for TrainPlex Phase 1 Step 4.2-8 — Quality alert center.
#
# Adds `htx_quality_alert` so reviewer-disagreement / time-anomaly /
# duplicate-answer-pattern signals can be auto-flagged for admin triage.
# See `core/models_alerts.py` for the model + `core/services/quality_anomaly_detector.py`
# for the detection helpers.
#
# Numbering: core has 4 prior migrations (0001..0004); this is the next in
# the sequence. The Phase 1 plan refers to it relative to the users-app
# counter — in the core app it lands at 0005.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_whatsapp_broadcast_log'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='QualityAlert',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'trigger_type',
                    models.CharField(
                        choices=[
                            ('reviewer_disagree', 'Reviewer disagreement'),
                            ('time_anomaly', 'Time anomaly (too fast submission)'),
                            ('duplicate_pattern', 'Duplicate answer pattern'),
                            ('reviewer_conflict', 'Reviewer conflict on golden task'),
                            ('cert_failed', 'Certification attempt failed'),
                        ],
                        help_text='Why the detector flagged this submission/trainer.',
                        max_length=32,
                    ),
                ),
                (
                    'submission_id',
                    models.IntegerField(
                        blank=True,
                        help_text=(
                            'Specific submission id this alert refers to. Nullable for '
                            'pattern alerts that span many submissions.'
                        ),
                        null=True,
                    ),
                ),
                (
                    'severity',
                    models.CharField(
                        choices=[
                            ('low', 'Low'),
                            ('medium', 'Medium'),
                            ('high', 'High'),
                            ('critical', 'Critical'),
                        ],
                        default='medium',
                        help_text='Severity bucket. Drives badge colour + dashboard widget counts.',
                        max_length=16,
                    ),
                ),
                (
                    'details',
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text=(
                            "Free-shape JSON with the detector's inputs — e.g. "
                            '{"time_taken_sec": 8, "expected_min_sec": 60}.'
                        ),
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('open', 'Open'),
                            ('reviewed', 'Reviewed (no action)'),
                            ('dismissed', 'Dismissed (false positive)'),
                            ('action_taken', 'Action taken'),
                        ],
                        default='open',
                        help_text='Open until an admin reviews it.',
                        max_length=20,
                    ),
                ),
                (
                    'reviewed_at',
                    models.DateTimeField(
                        blank=True,
                        help_text='When the admin resolved it. Set together with reviewed_by.',
                        null=True,
                    ),
                ),
                (
                    'resolution_notes',
                    models.TextField(
                        blank=True,
                        default='',
                        help_text='Free-text admin note explaining what was done.',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'reviewed_by',
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            'Admin who resolved the alert (set when status changes off open).'
                        ),
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='quality_alerts_reviewed',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'trainer',
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            'The trainer flagged by the alert. Nullable so a hard-deleted '
                            'trainer does not orphan-purge the audit trail.'
                        ),
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='quality_alerts',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Quality alert',
                'verbose_name_plural': 'Quality alerts',
                'db_table': 'htx_quality_alert',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['status', '-created_at'], name='htx_qa_status_idx'),
                    models.Index(fields=['severity', '-created_at'], name='htx_qa_severity_idx'),
                    models.Index(fields=['trigger_type', '-created_at'], name='htx_qa_trigger_idx'),
                    models.Index(fields=['trainer', '-created_at'], name='htx_qa_trainer_idx'),
                ],
            },
        ),
    ]
