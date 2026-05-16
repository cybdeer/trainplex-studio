# TrainPlex Codex audit M7 (2026-05-16) — promote trainer profile fields to
# first-class columns on the User model.
#
# Pre-M7 storage: state / city / pincode / language / tier lived inside
# ``User.custom_hotkeys['__trainplex_profile']`` (JSON blob shim). The
# Codex audit flagged this as needing first-class column storage so the
# fields are queryable, indexable, and visible in the admin UI.
#
# This migration:
#   1. Adds five new columns to ``htx_user`` with safe defaults so existing
#      rows back-fill without a manual ALTER.
#   2. Runs a data migration that lifts values out of every existing user's
#      ``custom_hotkeys['__trainplex_profile']`` blob into the new columns.
#   3. Leaves the JSON blob in place (forward-compat fallback) — Phase 2 can
#      drop the blob once api_profile.py is fully switched over.
#
# Safe to run on a populated DB: the data step iterates User rows in pages
# and is idempotent (skips users without the JSON namespace, never writes
# over an already-set first-class column).

from django.db import migrations, models


def _forward_copy_profile_meta(apps, schema_editor):
    """Copy ``custom_hotkeys['__trainplex_profile']`` values to new columns."""
    User = apps.get_model('users', 'User')
    META_KEY = '__trainplex_profile'
    FIELDS = ('state', 'city', 'pincode', 'language', 'tier')

    # Batched iteration so a large user table doesn't OOM.
    qs = User.objects.all().only(
        'id', 'custom_hotkeys',
        'state', 'city', 'pincode', 'language', 'tier',
    ).iterator(chunk_size=500)

    for user in qs:
        hotkeys = user.custom_hotkeys or {}
        if not isinstance(hotkeys, dict):
            continue
        meta = hotkeys.get(META_KEY) or {}
        if not isinstance(meta, dict) or not meta:
            continue
        dirty = False
        for field in FIELDS:
            value = meta.get(field)
            if value in (None, ''):
                continue
            current = getattr(user, field, '') or ''
            if current:
                # Don't trample anything an admin may have already typed in.
                continue
            # Coerce to string + truncate to column max so the save() never
            # throws on a stale blob with a huge value.
            value_str = str(value)
            max_lengths = {
                'state': 64,
                'city': 64,
                'pincode': 10,
                'language': 8,
                'tier': 16,
            }
            setattr(user, field, value_str[: max_lengths[field]])
            dirty = True
        if dirty:
            user.save(update_fields=list(FIELDS))


def _reverse_noop(apps, schema_editor):
    """Reverse migration is a no-op — column values stay; downstream rollback
    re-creates the columns if needed via the schema reverse step."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0014_user_2fa_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='state',
            field=models.CharField(
                max_length=64,
                blank=True,
                default='',
                help_text='Trainer profile: Indian state (Codex M7 first-class column).',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='city',
            field=models.CharField(
                max_length=64,
                blank=True,
                default='',
                help_text='Trainer profile: city (Codex M7 first-class column).',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='pincode',
            field=models.CharField(
                max_length=10,
                blank=True,
                default='',
                help_text='Trainer profile: postal pincode (Codex M7 first-class column).',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='language',
            field=models.CharField(
                max_length=8,
                blank=True,
                default='en',
                help_text='Trainer profile: preferred UI language (Codex M7 first-class column).',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='tier',
            field=models.CharField(
                max_length=16,
                blank=True,
                default='bronze',
                help_text='Trainer profile: tier badge (Codex M7 first-class column).',
            ),
        ),
        migrations.RunPython(_forward_copy_profile_meta, _reverse_noop),
    ]
