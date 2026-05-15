"""Generated for TrainPlex Phase 1 Step 14 — Global Search (Cmd+K).

Adds Postgres ``to_tsvector`` GIN indexes for the Cmd+K command palette so
the founder + admin can instant-search trainers, projects, audit logs and
tasks across the whole platform.

What it creates (Postgres only)
-------------------------------
- ``htx_users_fts_idx`` on ``users.User`` over (first_name || last_name || email)
- ``htx_projects_fts_idx`` on ``project.Project`` over (title || description)
- ``htx_audit_log_fts_idx`` on ``users.AuditLog`` over (action || actor email join)
- ``htx_tasks_fts_idx`` on ``task.Task`` over (data::text)

Why GIN
-------
``to_tsvector('simple', ...)`` returns a ``tsvector``; GIN is the only
index type that gives lookup acceleration on the ``@@`` match operator.
``CONCURRENTLY`` is skipped — we run this in a Django migration transaction;
in production the rollout DBA can re-create the index ``CONCURRENTLY`` later
if downtime matters (the per-table sizes here are small enough — < 50k rows
expected through Phase 2 — that an in-transaction CREATE INDEX is fine).

Why ``'simple'`` config (not ``'english'`` or ``'hindi'``)
----------------------------------------------------------
- ``'english'`` stemmer drops "ing" / "ed" suffixes which we don't want
  for proper nouns ("Geeta", "Priya") or transliterated Hindi terms.
- ``'hindi'`` config does not ship in stock Postgres. Custom dicts are
  Phase 2 / Step 8 work (when we install ``postgres-hindi`` extension).
- ``'simple'`` lower-cases + token-splits and otherwise keeps every token
  — perfect for substring-ish search on Indian names + project codes +
  audit IPs.

SQLite dev
----------
SQLite has FTS5 but the syntax is different. To keep this migration
single-file we make the SQL **conditional on the connection vendor** —
running on SQLite is a no-op. Tests + dev local boxes run on SQLite and
the Cmd+K view falls back to an ``icontains`` chain (handled in the view,
not here). Production Postgres gets the GIN index.

Phase 1 status
--------------
The indexes exist after this migration but the view
``core.views_search.AdminGlobalSearchAPI`` still returns MOCK data — it
does NOT yet query ``to_tsvector``. The migration goes in now so the
schema is staged for the Phase 2 swap; only the inner ``_search_mock_dataset``
call site changes when real wiring lands.
"""

from django.db import connection, migrations


# Raw-SQL bodies. Each is wrapped in an ``IF`` so the migration is safe
# to re-run (CREATE INDEX IF NOT EXISTS).
SQL_USERS_FTS = """
CREATE INDEX IF NOT EXISTS htx_users_fts_idx
ON htx_user
USING GIN (
    to_tsvector(
        'simple',
        COALESCE(first_name, '') || ' ' ||
        COALESCE(last_name, '') || ' ' ||
        COALESCE(email, '')
    )
);
"""

SQL_USERS_FTS_REVERSE = """
DROP INDEX IF EXISTS htx_users_fts_idx;
"""

SQL_PROJECTS_FTS = """
CREATE INDEX IF NOT EXISTS htx_projects_fts_idx
ON project
USING GIN (
    to_tsvector(
        'simple',
        COALESCE(title, '') || ' ' ||
        COALESCE(description, '')
    )
);
"""

SQL_PROJECTS_FTS_REVERSE = """
DROP INDEX IF EXISTS htx_projects_fts_idx;
"""

# AuditLog: index ``action`` + a deterministic representation of who.
# We can't JOIN inside an index expression — but ``action`` plus
# ``target_type`` / ``target_id`` text gives us the queryable hot path.
SQL_AUDIT_FTS = """
CREATE INDEX IF NOT EXISTS htx_audit_log_fts_idx
ON htx_audit_log
USING GIN (
    to_tsvector(
        'simple',
        COALESCE(action, '') || ' ' ||
        COALESCE(target_type, '') || ' ' ||
        COALESCE(target_id, '') || ' ' ||
        COALESCE(ip_address::text, '')
    )
);
"""

SQL_AUDIT_FTS_REVERSE = """
DROP INDEX IF EXISTS htx_audit_log_fts_idx;
"""

# Task.data is JSONB in Postgres — cast to text for a generic GIN.
# For per-key search the right play is a separate ``data jsonb_path_ops``
# GIN, but that's a Phase 2 concern. For Cmd+K we want substring on the
# label text.
SQL_TASKS_FTS = """
CREATE INDEX IF NOT EXISTS htx_tasks_fts_idx
ON task
USING GIN (
    to_tsvector('simple', COALESCE(data::text, ''))
);
"""

SQL_TASKS_FTS_REVERSE = """
DROP INDEX IF EXISTS htx_tasks_fts_idx;
"""


def _run_if_postgres(forward_sql, reverse_sql):
    """Return a (forward, reverse) pair of callables that no-op on SQLite.

    ``RunSQL`` with a literal string would fail on SQLite (``USING GIN`` is
    Postgres-only). Using a callable lets us branch on the connection
    vendor at apply-time.
    """

    def forward(_apps, _schema_editor):
        if connection.vendor == 'postgresql':
            with connection.cursor() as cur:
                cur.execute(forward_sql)
        # SQLite / MySQL → no-op (dev local + tests run here)

    def reverse(_apps, _schema_editor):
        if connection.vendor == 'postgresql':
            with connection.cursor() as cur:
                cur.execute(reverse_sql)

    return forward, reverse


_users_fwd, _users_rev = _run_if_postgres(SQL_USERS_FTS, SQL_USERS_FTS_REVERSE)
_projects_fwd, _projects_rev = _run_if_postgres(
    SQL_PROJECTS_FTS, SQL_PROJECTS_FTS_REVERSE
)
_audit_fwd, _audit_rev = _run_if_postgres(SQL_AUDIT_FTS, SQL_AUDIT_FTS_REVERSE)
_tasks_fwd, _tasks_rev = _run_if_postgres(SQL_TASKS_FTS, SQL_TASKS_FTS_REVERSE)


class Migration(migrations.Migration):
    """Phase 1 Step 14 — Cmd+K FTS indexes.

    Dependencies pin the latest migrations of every app whose table this
    migration touches so Django doesn't try to apply the GIN index before
    the underlying column exists.
    """

    dependencies = [
        # Newest core migration before this one.
        ('core', '0005_quality_alert'),
        # AuditLog (``htx_audit_log``) was added in users.0013; 2FA fields
        # came in 0014. We pin the latest leaf so the index call site is
        # safe even if a fresh fork applies them out of order.
        ('users', '0014_user_2fa_fields'),
        # Project + Task tables — title / description / data have lived
        # on the initial schema since day one of LS upstream.
        ('projects', '0001_squashed_0065_auto_20210223_2014'),
        ('tasks', '0001_squashed_0041_taskcompletionhistory_was_cancelled'),
    ]

    operations = [
        migrations.RunPython(_users_fwd, _users_rev),
        migrations.RunPython(_projects_fwd, _projects_rev),
        migrations.RunPython(_audit_fwd, _audit_rev),
        migrations.RunPython(_tasks_fwd, _tasks_rev),
    ]
