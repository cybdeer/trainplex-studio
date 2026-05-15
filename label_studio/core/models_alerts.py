"""TrainPlex quality-alert models — Phase 1 Step 4.2-8.

Sibling module to ``core/models.py`` so its schema stays focused on the
upstream Label Studio core. Imported back into ``core/models.py`` at the
bottom so Django's app loader registers the table under the ``core`` app
(same pattern used by `core/models_broadcast.py`).

Tables
------
* ``htx_quality_alert`` — one row per auto-detected quality / fraud /
  reviewer-disagreement signal. Created by
  ``core/services/quality_anomaly_detector.py``. Resolved by an admin
  via ``POST /api/v1/admin/quality-alerts/<id>/review``.

Wiring note (mock vs real, Phase 1 vs Week 5)
---------------------------------------------
Phase 1 ships the model + service + admin endpoints with **mock detection
inputs**. The hooks that call `flag_*` functions from the live submission
pipeline (peer-review and certification submit paths) only become real
when peer-review native lands in Week 5. Until then the table is exercised
by tests + admin-initiated synthetic calls; the data shape is locked here
so the Week 5 swap is a 1-call wire-up, not a schema migration.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class QualityAlert(models.Model):
    """Append-once / update-once row for an admin to review.

    Lifecycle
    ---------
    * created → ``status='open'``
    * admin acts → ``status`` flips to one of
      ``reviewed`` / ``dismissed`` / ``action_taken`` and
      ``reviewed_by`` / ``reviewed_at`` / ``resolution_notes`` populate.

    The ``submission_id`` column is a plain integer FK-by-value; we don't
    add a hard FK because submissions live in `tasks.Annotation` /
    `tasks.Task` (and possibly a Phase 2 peer-review table) and the lookup
    is loose by design — an alert about a deleted submission should still
    surface to the admin so the audit trail isn't silently broken.
    """

    # ---- trigger_type enum ----
    TRIGGER_REVIEWER_DISAGREE = 'reviewer_disagree'
    TRIGGER_TIME_ANOMALY = 'time_anomaly'
    TRIGGER_DUPLICATE_PATTERN = 'duplicate_pattern'
    TRIGGER_REVIEWER_CONFLICT = 'reviewer_conflict'
    TRIGGER_CERT_FAILED = 'cert_failed'

    TRIGGER_CHOICES = [
        (TRIGGER_REVIEWER_DISAGREE, 'Reviewer disagreement'),
        (TRIGGER_TIME_ANOMALY, 'Time anomaly (too fast submission)'),
        (TRIGGER_DUPLICATE_PATTERN, 'Duplicate answer pattern'),
        (TRIGGER_REVIEWER_CONFLICT, 'Reviewer conflict on golden task'),
        (TRIGGER_CERT_FAILED, 'Certification attempt failed'),
    ]

    # ---- severity enum ----
    SEVERITY_LOW = 'low'
    SEVERITY_MEDIUM = 'medium'
    SEVERITY_HIGH = 'high'
    SEVERITY_CRITICAL = 'critical'

    SEVERITY_CHOICES = [
        (SEVERITY_LOW, 'Low'),
        (SEVERITY_MEDIUM, 'Medium'),
        (SEVERITY_HIGH, 'High'),
        (SEVERITY_CRITICAL, 'Critical'),
    ]

    # ---- status enum ----
    STATUS_OPEN = 'open'
    STATUS_REVIEWED = 'reviewed'
    STATUS_DISMISSED = 'dismissed'
    STATUS_ACTION_TAKEN = 'action_taken'

    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_REVIEWED, 'Reviewed (no action)'),
        (STATUS_DISMISSED, 'Dismissed (false positive)'),
        (STATUS_ACTION_TAKEN, 'Action taken'),
    ]

    trigger_type = models.CharField(
        max_length=32,
        choices=TRIGGER_CHOICES,
        help_text=_('Why the detector flagged this submission/trainer.'),
    )

    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quality_alerts',
        help_text=_('The trainer flagged by the alert. Nullable so a hard-deleted '
                    'trainer does not orphan-purge the audit trail.'),
    )

    submission_id = models.IntegerField(
        null=True,
        blank=True,
        help_text=_('Specific submission id this alert refers to. Nullable for '
                    'pattern alerts that span many submissions.'),
    )

    severity = models.CharField(
        max_length=16,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_MEDIUM,
        help_text=_('Severity bucket. Drives badge colour + dashboard widget counts.'),
    )

    details = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Free-shape JSON with the detector\'s inputs — e.g. '
                    '{"time_taken_sec": 8, "expected_min_sec": 60}.'),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        help_text=_('Open until an admin reviews it.'),
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quality_alerts_reviewed',
        help_text=_('Admin who resolved the alert (set when status changes off open).'),
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When the admin resolved it. Set together with reviewed_by.'),
    )

    resolution_notes = models.TextField(
        blank=True,
        default='',
        help_text=_('Free-text admin note explaining what was done.'),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'htx_quality_alert'
        verbose_name = _('Quality alert')
        verbose_name_plural = _('Quality alerts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['severity', '-created_at']),
            models.Index(fields=['trigger_type', '-created_at']),
            models.Index(fields=['trainer', '-created_at']),
        ]

    def __str__(self):  # pragma: no cover  (display only)
        return (
            f'QualityAlert(id={self.id}, trigger={self.trigger_type}, '
            f'severity={self.severity}, status={self.status}, '
            f'trainer_id={self.trainer_id})'
        )
