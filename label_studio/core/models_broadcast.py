"""TrainPlex broadcast / outbound messaging models — Phase 1 Step 4.2-7.

Kept in a sibling module to ``core/models.py`` so the AsyncMigrationStatus
churn there doesn't conflict with admin-only broadcast schema; Django picks
up the model via the ``core.models_broadcast`` import in ``core/apps.py``
(or via the explicit import inside the service module + the migration).

Tables
------
* ``htx_wa_broadcast_log`` — one row per (admin, template, trainer) attempt.
  Statuses: ``queued`` / ``sent`` / ``failed`` / ``skipped``. The skipped row
  exists so the founder can see "I tried to fan-out, X went out, Y were
  deduped" on the history drawer.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class WhatsAppBroadcastLog(models.Model):
    """Append-only log of every WhatsApp template fan-out attempt.

    Phase 1 stores **all** rows (sent / failed / skipped) so the admin can
    see what happened on the history drawer. Retention policy is the same
    as `AuditLog`: 2 years, cleanup cron in Phase 2.
    """

    STATUS_QUEUED = 'queued'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_SKIPPED = 'skipped'

    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_SKIPPED, 'Skipped (recent duplicate)'),
    ]

    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wa_broadcasts_fired',
        help_text=_('The admin who fired the broadcast.'),
    )

    template_id = models.CharField(
        max_length=64,
        help_text=_('Internal template slug — one of `KNOWN_TEMPLATES`.'),
    )

    # We keep both a FK to the trainer User and a plain integer copy of
    # the id. The integer survives a trainer being hard-deleted later, so
    # the audit trail still says "we attempted to send to trainer #87" even
    # after their User row is gone.
    trainer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wa_broadcasts_received',
        help_text=_('The trainer that was the target of the send.'),
    )
    trainer_id_value = models.IntegerField(
        help_text=_('Trainer user id at time of send — preserved even if the User row is later deleted.'),
    )

    mobile_number = models.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text=_('Mobile number that was actually called (digits + country code).'),
    )

    params = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('AiSensy templateParams sent for this row.'),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )

    aisensy_message_id = models.CharField(
        max_length=128,
        blank=True,
        default='',
        help_text=_('Provider-side message id returned by AiSensy. Mock value in Phase 1.'),
    )

    error = models.TextField(
        blank=True,
        default='',
        help_text=_('Free-text error reason on failed / skipped rows.'),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'htx_wa_broadcast_log'
        verbose_name = _('WhatsApp broadcast log entry')
        verbose_name_plural = _('WhatsApp broadcast log entries')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin', '-created_at']),
            models.Index(fields=['template_id', '-created_at']),
            models.Index(fields=['trainer_user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):  # pragma: no cover  (display only)
        return (
            f'WhatsAppBroadcastLog(template={self.template_id}, '
            f'trainer_id={self.trainer_id_value}, status={self.status}, '
            f'at={self.created_at:%Y-%m-%d %H:%M:%S})'
        )
