# Generated for TrainPlex Phase 1 Step 4.2-7 — WhatsApp broadcast log.
#
# Adds `htx_wa_broadcast_log` so every admin WA template fan-out attempt
# (sent / failed / skipped) is logged. See `core/models_broadcast.py` for
# the model + `core/services/wa_broadcast.py` for the service that writes it.
#
# NOTE on numbering: core has 3 prior migrations (0001..0003); this is the
# next in the sequence. The Phase 1 plan refers to it as "0015" relative to
# the users-app counter — in the core app it lands at 0004.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_asyncmigrationstatus_add_scheduled_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WhatsAppBroadcastLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'template_id',
                    models.CharField(
                        help_text='Internal template slug — one of `KNOWN_TEMPLATES`.',
                        max_length=64,
                    ),
                ),
                (
                    'trainer_id_value',
                    models.IntegerField(
                        help_text='Trainer user id at time of send — preserved even if the User row is later deleted.',
                    ),
                ),
                (
                    'mobile_number',
                    models.CharField(
                        blank=True,
                        default='',
                        help_text='Mobile number that was actually called (digits + country code).',
                        max_length=32,
                    ),
                ),
                (
                    'params',
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text='AiSensy templateParams sent for this row.',
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('queued', 'Queued'),
                            ('sent', 'Sent'),
                            ('failed', 'Failed'),
                            ('skipped', 'Skipped (recent duplicate)'),
                        ],
                        default='queued',
                        max_length=20,
                    ),
                ),
                (
                    'aisensy_message_id',
                    models.CharField(
                        blank=True,
                        default='',
                        help_text='Provider-side message id returned by AiSensy. Mock value in Phase 1.',
                        max_length=128,
                    ),
                ),
                (
                    'error',
                    models.TextField(
                        blank=True,
                        default='',
                        help_text='Free-text error reason on failed / skipped rows.',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'admin',
                    models.ForeignKey(
                        blank=True,
                        help_text='The admin who fired the broadcast.',
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='wa_broadcasts_fired',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'trainer_user',
                    models.ForeignKey(
                        blank=True,
                        help_text='The trainer that was the target of the send.',
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='wa_broadcasts_received',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'WhatsApp broadcast log entry',
                'verbose_name_plural': 'WhatsApp broadcast log entries',
                'db_table': 'htx_wa_broadcast_log',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['admin', '-created_at'], name='htx_wa_broa_admin_i_29c5a0_idx'),
                    models.Index(fields=['template_id', '-created_at'], name='htx_wa_broa_templat_8b3e77_idx'),
                    models.Index(fields=['trainer_user', '-created_at'], name='htx_wa_broa_trainer_bcd080_idx'),
                    models.Index(fields=['status', '-created_at'], name='htx_wa_broa_status_21e444_idx'),
                ],
            },
        ),
    ]
