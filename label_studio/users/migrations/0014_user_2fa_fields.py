# TrainPlex Phase 1 Step 12.4 — User 2FA scaffold.
# Adds TOTP secret + enabled flag + backup codes (hashed) to User.
# Login-flow wire-in is the next agent's job; this migration just lands
# the columns so the rest of the Security Baseline can ship together.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0013_audit_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='totp_secret',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Base32-encoded TOTP shared secret. Empty until the user enrolls.',
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='totp_enabled',
            field=models.BooleanField(
                default=False,
                help_text='True once the user has confirmed their authenticator app with a valid code.',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='backup_codes',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='List of SHA-256-hashed single-use recovery codes. Each code is removed when consumed.',
            ),
        ),
    ]
