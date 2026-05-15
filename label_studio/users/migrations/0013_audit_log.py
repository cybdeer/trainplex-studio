# TrainPlex Phase 1 Step 12.3 — AuditLog table.
# Append-only audit trail for login attempts, permission changes,
# hard deletes, and admin actions. Retention 2y (cleanup cron — Phase 2).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0012_add_role_field'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'action',
                    models.CharField(
                        choices=[
                            ('login_success', 'Login success'),
                            ('login_fail', 'Login failure'),
                            ('permission_change', 'Permission change'),
                            ('delete', 'Delete'),
                            ('admin_action', 'Admin action'),
                        ],
                        max_length=64,
                    ),
                ),
                (
                    'target_type',
                    models.CharField(
                        blank=True,
                        help_text='Object class name affected — e.g. "User", "Project", "Annotation".',
                        max_length=64,
                    ),
                ),
                (
                    'target_id',
                    models.CharField(
                        blank=True,
                        help_text='PK of the affected object, stored as a string so non-int PKs (UUIDs) fit.',
                        max_length=64,
                    ),
                ),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('success', models.BooleanField(default=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'user',
                    models.ForeignKey(
                        blank=True,
                        help_text='Actor / subject of the event. NULL for failed logins where the user is unknown.',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='audit_events',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'audit log entry',
                'verbose_name_plural': 'audit log entries',
                'db_table': 'htx_audit_log',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', '-created_at'], name='htx_audit_l_user_id_idx'),
                    models.Index(fields=['action', '-created_at'], name='htx_audit_l_action_idx'),
                    models.Index(fields=['-created_at'], name='htx_audit_l_created_idx'),
                ],
            },
        ),
    ]
