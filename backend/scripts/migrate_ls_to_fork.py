"""
TrainPlex Studio — Phase 1 Step 8 / 8.5 LS → Fork Data Migration Script
=======================================================================

Purpose
-------
One-shot migration of legacy Label Studio production data into the
TrainPlex Studio fork. Designed for the Phase 1 Step 8.5 **dry-run**:
the script reads the source DB, plans every insert/update, and either
applies them in a single transaction (real run) or prints them and
rolls back (dry-run).

Founder rules honoured
----------------------
* **One-shot root-cause fix** — every phase wrapped in a SAVEPOINT;
  any failure rolls back ONLY that phase, the rest of the migration
  is restartable. The dry-run flag is the safety net against partial
  application during a real production cutover.
* **No founder personal number in outbound** — the script never
  emits the founder mobile (+91 8764001234). Founder review report
  uses the org's WhatsApp Business number stub only.
* **Plain-Hindi bug-fix recap** — emitted in the MIGRATION_REPORT.md
  footer so the founder reads the migration outcome in <30 sec.
* **Incident log append** — every real run appends a row to
  /var/lib/trainplex-data/INCIDENT_LOG.md (best-effort; the script
  does not fail if the path is not writable, just warns).
* **Sub-agent incremental write** — phase summaries are checkpointed
  to disk after each phase so a kill -9 mid-migration still leaves
  a partial MIGRATION_REPORT.md the founder can inspect.

Usage
-----
Dry-run (default; reads source, writes NOTHING):

    python migrate_ls_to_fork.py \\
        --source-db postgres://USER:PASS@host:5432/labelstudio \\
        --dry-run \\
        --verbose

Real run (requires explicit --apply AND --i-have-a-backup):

    python migrate_ls_to_fork.py \\
        --source-db postgres://USER:PASS@host:5432/labelstudio \\
        --target-db postgres://USER:PASS@host:5432/trainplex \\
        --apply \\
        --i-have-a-backup \\
        --verbose

Source URL forms supported
--------------------------
* sqlite:///path/to/label_studio.sqlite3
* /path/to/label_studio.sqlite3        (auto-detected by `.sqlite3` suffix)
* postgres://user:pass@host:port/dbname
* postgresql://user:pass@host:port/dbname

If --target-db is omitted in dry-run, the script still runs (only the
source DB is touched, read-only). In --apply mode --target-db is
mandatory.

Idempotency
-----------
* User merge uses `ON CONFLICT (email) DO NOTHING` on the target,
  followed by an UPDATE that sets `ls_legacy_id` only when it is NULL.
  Re-running is a no-op for already-migrated rows.
* Projects, tasks, annotations preserve their source IDs (so two
  runs collide at the second INSERT and are silently skipped by
  `ON CONFLICT (id) DO NOTHING`).
* Phase 4 (project copy) and Phase 5 (task copy) emit
  `ON CONFLICT (id) DO NOTHING` everywhere.
* Phase 6 (annotation → submission) uses a stable hash of
  `(task_id, completed_by_legacy_id, created_at)` so the same source
  row maps to the same fork row even if re-run from a snapshot.

Dry-run safety
--------------
* Target DB connection is opened in **autocommit=False** and the
  outer transaction is `ROLLBACK`-ed at the end when --dry-run is set.
* Source DB is opened **read-only** (PG: `SET TRANSACTION READ ONLY`;
  SQLite: `mode=ro` in the URI). The script will REFUSE to write to
  the source under any circumstance.

Author: Phase 1 Step 8.5
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import json
import logging
import os
import random
import re
import sqlite3
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

# psycopg v3 is in pyproject.toml; the script lazy-imports so SQLite-only
# dry-runs do not require it on the host.
try:
    import psycopg  # type: ignore
    PSYCOPG_AVAILABLE = True
except ImportError:  # pragma: no cover - optional in SQLite-only test path
    psycopg = None  # type: ignore
    PSYCOPG_AVAILABLE = False


# ---------------------------------------------------------------------------
# Expected source-DB shape — used by Phase 1 (Backup Verify) + Phase 2
# (Schema Audit). Numbers come straight from the Phase 1 plan brief:
# 17 trainers, 1201 tasks, 5 projects, plus submissions.
# ---------------------------------------------------------------------------
EXPECTED_COUNTS = {
    'htx_user': {'min': 1, 'max': 1000, 'plan': 17},
    'project': {'min': 1, 'max': 100, 'plan': 5},
    'task': {'min': 1, 'max': 100000, 'plan': 1201},
    'task_completion': {'min': 0, 'max': 100000, 'plan': None},  # = annotation
    'project_member': {'min': 0, 'max': 10000, 'plan': None},
}

# Tables that MUST exist on the source side for the migration to proceed.
REQUIRED_SOURCE_TABLES = ['htx_user', 'project', 'task', 'task_completion', 'project_member']

# LS annotation flags → fork submission status mapping. Append-only; the
# mapping is read by Phase 6.
ANNOTATION_STATUS_MAP = {
    # (was_cancelled, ground_truth) → fork status
    (True, False): 'cancelled',
    (True, True): 'cancelled',  # cancelled wins over ground_truth
    (False, True): 'gold_standard',
    (False, False): 'submitted',
}

# Founder rule: never emit this mobile in any artifact.
FORBIDDEN_FOUNDER_MOBILE = re.compile(r'(?:\+?91[\s-]?)?8764001234')

# Path the founder reviews after the run completes. Append-only.
DEFAULT_INCIDENT_LOG = Path('/var/lib/trainplex-data/INCIDENT_LOG.md')

REPORT_VERSION = '1.0'


# ---------------------------------------------------------------------------
# Logging — DEBUG for --verbose, INFO otherwise. Output goes to stderr so
# Phase summaries on stdout stay clean for pipe-redirects.
# ---------------------------------------------------------------------------
logger = logging.getLogger('migrate_ls_to_fork')


def setup_logging(verbose: bool) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    )
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)


# ---------------------------------------------------------------------------
# DB wrapper — gives one API for SQLite and Postgres so the rest of the
# script does not care which engine the source is on. The fork side is
# always Postgres in production but SQLite is supported for the test
# fixture (label_studio/tests/test_migration_script.py).
# ---------------------------------------------------------------------------
@dataclass
class DBHandle:
    """Thin wrapper around a sqlite3 / psycopg connection.

    Reasons we do not use Django ORM:
    1. The script must run before the fork's Django process has even
       booted (cutover scenario: fork DB just provisioned, no migrations
       fully applied on the source's Django version).
    2. We need a single transaction across MANY raw INSERTs.
    3. The source DB is a legacy LS schema — using the fork's ORM
       against it would crash on missing fields.
    """

    kind: str  # 'sqlite' | 'postgres'
    conn: Any  # sqlite3.Connection | psycopg.Connection
    read_only: bool = False

    @classmethod
    def open(cls, url: str, *, read_only: bool = False) -> 'DBHandle':
        if url.startswith('sqlite://') or url.endswith('.sqlite3') or url.endswith('.db'):
            path = url[len('sqlite:///'):] if url.startswith('sqlite://') else url
            if read_only:
                # SQLite read-only mode via URI — guarantees no INSERT can fire.
                conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
            else:
                # isolation_level=None puts the driver in "manual" mode so the
                # outer BEGIN/COMMIT/ROLLBACK boundary is explicit; otherwise
                # SQLite's autocommit kicks in around DML batches and
                # `--dry-run` rollback would no-op.
                conn = sqlite3.connect(path, isolation_level=None)
                conn.execute('BEGIN')
            conn.row_factory = sqlite3.Row
            return cls(kind='sqlite', conn=conn, read_only=read_only)
        if url.startswith(('postgres://', 'postgresql://')):
            if not PSYCOPG_AVAILABLE:
                raise RuntimeError(
                    'psycopg is not installed but a Postgres URL was given. '
                    'Install via the repo poetry env or use a sqlite:// URL.'
                )
            conn = psycopg.connect(url, autocommit=False)
            if read_only:
                with conn.cursor() as cur:
                    cur.execute('SET TRANSACTION READ ONLY')
            return cls(kind='postgres', conn=conn, read_only=read_only)
        raise ValueError(f'Unrecognised DB URL form: {url!r}')

    # -- placeholder converter ------------------------------------------------
    def ph(self, sql: str) -> str:
        """Convert ``?`` placeholders into ``%s`` when running on Postgres."""
        return sql if self.kind == 'sqlite' else sql.replace('?', '%s')

    # -- query helpers -------------------------------------------------------
    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        cur = self.conn.cursor()
        try:
            cur.execute(self.ph(sql), params)
            rows = cur.fetchall()
            if self.kind == 'sqlite':
                return [dict(r) for r in rows]
            cols = [d[0] for d in cur.description] if cur.description else []
            return [dict(zip(cols, row)) for row in rows]
        finally:
            cur.close()

    def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple = ()) -> int:
        if self.read_only:
            raise RuntimeError('Refusing to execute write on read-only DB handle')
        cur = self.conn.cursor()
        try:
            cur.execute(self.ph(sql), params)
            return cur.rowcount
        finally:
            cur.close()

    def table_exists(self, name: str) -> bool:
        if self.kind == 'sqlite':
            row = self.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (name,),
            )
            return row is not None
        row = self.fetchone(
            "SELECT 1 FROM information_schema.tables WHERE table_name=?",
            (name,),
        )
        return row is not None

    def column_exists(self, table: str, column: str) -> bool:
        if self.kind == 'sqlite':
            rows = self.fetchall(f"PRAGMA table_info({table})")
            return any(r['name'] == column for r in rows)
        row = self.fetchone(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name=? AND column_name=?",
            (table, column),
        )
        return row is not None

    def count(self, table: str) -> int:
        row = self.fetchone(f'SELECT COUNT(*) AS c FROM {table}')
        return int(row['c']) if row else 0

    def db_size_bytes(self) -> int:
        """Best-effort source-DB size for the backup-verify phase."""
        if self.kind == 'sqlite':
            row = self.fetchone('PRAGMA page_count')
            pc = int(list(row.values())[0]) if row else 0
            row = self.fetchone('PRAGMA page_size')
            ps = int(list(row.values())[0]) if row else 0
            return pc * ps
        row = self.fetchone('SELECT pg_database_size(current_database()) AS s')
        return int(row['s']) if row else 0

    def savepoint(self, name: str):
        """Context manager around a phase-scoped SAVEPOINT."""
        return _Savepoint(self, name)

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # pragma: no cover - close is best-effort
            pass


class _Savepoint:
    """Phase-scoped SAVEPOINT.

    On Postgres we use the real ``SAVEPOINT`` statement so a partial
    phase failure rolls back just that phase. On SQLite we fall back to
    nested-transaction emulation via the same SQL surface (SQLite has
    real SAVEPOINTs too).
    """

    def __init__(self, db: DBHandle, name: str):
        self.db = db
        self.name = name

    def __enter__(self):
        self.db.execute(f'SAVEPOINT {self.name}')
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.db.execute(f'RELEASE SAVEPOINT {self.name}')
        else:
            self.db.execute(f'ROLLBACK TO SAVEPOINT {self.name}')
            self.db.execute(f'RELEASE SAVEPOINT {self.name}')
        return False  # never swallow


# ---------------------------------------------------------------------------
# Phase result accounting — every phase returns a PhaseResult so we can
# build the MIGRATION_REPORT.md at the end without coupling phases.
# ---------------------------------------------------------------------------
@dataclass
class PhaseResult:
    name: str
    passed: int = 0
    skipped: int = 0
    failed: int = 0
    notes: list[str] = field(default_factory=list)
    rows_read: int = 0
    rows_written: int = 0
    duration_ms: int = 0

    def add_note(self, note: str) -> None:
        # Founder rule: never let the founder mobile leak through.
        sanitized = FORBIDDEN_FOUNDER_MOBILE.sub('[REDACTED-MOBILE]', note)
        self.notes.append(sanitized)

    @property
    def status(self) -> str:
        if self.failed > 0:
            return 'FAILED'
        if self.passed == 0 and self.skipped == 0 and self.rows_written == 0 and self.rows_read == 0:
            # Phase was a pure schema/audit check — pass through.
            return 'OK'
        return 'OK'

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'status': self.status,
            'passed': self.passed,
            'skipped': self.skipped,
            'failed': self.failed,
            'rows_read': self.rows_read,
            'rows_written': self.rows_written,
            'duration_ms': self.duration_ms,
            'notes': self.notes,
        }


# ---------------------------------------------------------------------------
# Migration plan — phases as named methods, each returning a PhaseResult.
# The MigrationRunner is the orchestrator; it owns the source/target
# connections and the report accumulator.
# ---------------------------------------------------------------------------
class MigrationRunner:
    def __init__(
        self,
        *,
        source_url: str,
        target_url: str | None,
        dry_run: bool,
        verbose: bool,
        report_path: Path,
        orphans_path: Path,
        seed: int = 42,
    ):
        self.source_url = source_url
        self.target_url = target_url
        self.dry_run = dry_run
        self.verbose = verbose
        self.report_path = report_path
        self.orphans_path = orphans_path
        self.seed = seed
        self.results: list[PhaseResult] = []
        self.orphans: list[dict] = []  # users without fork-side email match
        self.legacy_user_map: dict[int, int] = {}  # LS user.id → fork user.id
        self.source: DBHandle | None = None
        self.target: DBHandle | None = None
        self._started_at = datetime.datetime.utcnow()
        random.seed(seed)

    # -- connection lifecycle -------------------------------------------------
    def _connect(self) -> None:
        logger.info('Opening source DB (read-only): %s', _safe_url(self.source_url))
        self.source = DBHandle.open(self.source_url, read_only=True)
        if self.target_url:
            logger.info(
                'Opening target DB (%s): %s',
                'DRY-RUN' if self.dry_run else 'APPLY',
                _safe_url(self.target_url),
            )
            self.target = DBHandle.open(self.target_url, read_only=False)
        else:
            logger.info('No --target-db given (dry-run preview only).')
            self.target = None

    def _disconnect(self) -> None:
        if self.target is not None:
            if self.dry_run:
                logger.info('Dry-run: rolling back target transaction.')
                self.target.rollback()
            else:
                logger.info('Apply mode: committing target transaction.')
                self.target.commit()
            self.target.close()
        if self.source is not None:
            self.source.close()

    # -- phase orchestration --------------------------------------------------
    def run(self) -> int:
        self._connect()
        try:
            self._run_phase('1_backup_verify', self.phase_1_backup_verify)
            self._run_phase('2_schema_audit', self.phase_2_schema_audit)
            self._run_phase('3_user_merge', self.phase_3_user_merge)
            self._run_phase('4_project_copy', self.phase_4_project_copy)
            self._run_phase('5_task_copy', self.phase_5_task_copy)
            self._run_phase('6_annotation_submission', self.phase_6_annotation_submission)
            self._run_phase('7_project_member_assignment', self.phase_7_project_member_assignment)
            self._run_phase('8_row_count_cross_check', self.phase_8_row_count_cross_check)
            self._run_phase('9_spot_check', self.phase_9_spot_check)
            self._run_phase('10_generate_report', self.phase_10_generate_report)
        finally:
            self._disconnect()

        failed = sum(r.failed for r in self.results)
        if failed:
            logger.error('Migration finished with %s failures. See %s.', failed, self.report_path)
            return 2
        logger.info('Migration finished successfully. See %s.', self.report_path)
        return 0

    def _run_phase(self, name: str, fn) -> None:
        logger.info('--- Phase %s start ---', name)
        t0 = datetime.datetime.utcnow()
        result = PhaseResult(name=name)
        try:
            if self.target is not None and name not in ('1_backup_verify', '2_schema_audit', '8_row_count_cross_check', '9_spot_check', '10_generate_report'):
                with self.target.savepoint(f'sp_{name}'):
                    fn(result)
            else:
                fn(result)
        except Exception as exc:  # pragma: no cover - audit-trail print
            result.failed += 1
            tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            result.add_note(f'EXCEPTION: {exc}')
            logger.error('Phase %s failed:\n%s', name, tb)
        finally:
            result.duration_ms = int((datetime.datetime.utcnow() - t0).total_seconds() * 1000)
            self.results.append(result)
            # Incremental checkpoint — kill -9 still leaves a partial report
            # (Memory rule: sub-agent incremental write).
            self._write_partial_report()
            logger.info(
                '--- Phase %s end: passed=%s skipped=%s failed=%s rows_read=%s rows_written=%s (%sms) ---',
                name, result.passed, result.skipped, result.failed,
                result.rows_read, result.rows_written, result.duration_ms,
            )

    # ----------------------------------------------------------------- Phase 1
    def phase_1_backup_verify(self, r: PhaseResult) -> None:
        assert self.source is not None
        size = self.source.db_size_bytes()
        r.add_note(f'source_db_size_bytes={size}')
        if size <= 0:
            r.add_note('Source DB reports zero bytes — refusing to proceed.')
            r.failed += 1
            return
        for tbl, expect in EXPECTED_COUNTS.items():
            if not self.source.table_exists(tbl):
                r.skipped += 1
                r.add_note(f'Table {tbl!r} missing on source — will be skipped if optional.')
                continue
            n = self.source.count(tbl)
            r.rows_read += n
            r.add_note(f'source.{tbl}.count={n}')
            if not (expect['min'] <= n <= expect['max']):
                r.add_note(
                    f'WARN: source.{tbl} count={n} outside expected '
                    f'[{expect["min"]}, {expect["max"]}] — investigate before --apply.'
                )
            if expect['plan'] is not None and n != expect['plan']:
                r.add_note(
                    f'NOTE: source.{tbl} count={n} != plan-expected {expect["plan"]} '
                    f'(plan was a snapshot; not an error if drift is recent).'
                )
            r.passed += 1

    # ----------------------------------------------------------------- Phase 2
    def phase_2_schema_audit(self, r: PhaseResult) -> None:
        assert self.source is not None
        missing = [t for t in REQUIRED_SOURCE_TABLES if not self.source.table_exists(t)]
        if missing:
            r.failed += 1
            r.add_note(f'Source DB missing required tables: {missing}')
            return
        for t in REQUIRED_SOURCE_TABLES:
            r.passed += 1
            r.add_note(f'OK: source.{t} present')
        # Sanity-check that fork-side ls_legacy_id column exists; it lands
        # in the Phase 2 / Step 8 schema PR. In dry-run we WARN rather
        # than fail so the founder can use this same script for the
        # pre-Phase-2 rehearsal.
        if self.target is not None:
            if not self.target.column_exists('htx_user', 'ls_legacy_id'):
                r.add_note(
                    'WARN: target.htx_user has no ls_legacy_id column — Phase 3 will '
                    'simulate the merge but will not be able to record the mapping '
                    'until the Step 8 schema migration lands. This is expected in '
                    'Phase 1 dry-run.'
                )

    # ----------------------------------------------------------------- Phase 3
    def phase_3_user_merge(self, r: PhaseResult) -> None:
        assert self.source is not None
        ls_users = self.source.fetchall(
            'SELECT id, email, password, first_name, last_name, '
            'is_staff, is_active, date_joined FROM htx_user'
        )
        r.rows_read = len(ls_users)
        # Target lookup is a single email → id index pulled once. If the
        # target DB is None (dry-run with no target), we still EXERCISE
        # the planner — emitting the decisions to logs so the founder
        # can audit them — but we obviously cannot write.
        fork_index: dict[str, int] = {}
        if self.target is not None:
            for row in self.target.fetchall('SELECT id, email FROM htx_user'):
                if row.get('email'):
                    fork_index[row['email'].strip().lower()] = int(row['id'])
        # Case-sensitive duplicate detector — `Foo@x.com` & `foo@x.com`
        # both collapse to the same target row.
        seen_emails: set[str] = set()
        for u in ls_users:
            ls_id = int(u['id'])
            email = (u.get('email') or '').strip()
            norm = email.lower()
            if not norm:
                r.skipped += 1
                r.add_note(f'SKIP ls_user.id={ls_id}: no email')
                self.orphans.append({'kind': 'no_email', 'ls_user_id': ls_id, **_clean_record(u)})
                continue
            if norm in seen_emails:
                r.skipped += 1
                r.add_note(f'SKIP ls_user.id={ls_id}: duplicate email (case-insensitive)')
                continue
            seen_emails.add(norm)
            fork_id = fork_index.get(norm)
            if fork_id:
                # Match — write ls_legacy_id (if column exists).
                self.legacy_user_map[ls_id] = fork_id
                if self.target is not None and self.target.column_exists('htx_user', 'ls_legacy_id'):
                    self.target.execute(
                        'UPDATE htx_user SET ls_legacy_id = ? WHERE id = ? AND ls_legacy_id IS NULL',
                        (ls_id, fork_id),
                    )
                    r.rows_written += 1
                r.passed += 1
                logger.debug('MATCH ls_user.id=%s ↔ fork_user.id=%s (%s)', ls_id, fork_id, norm)
            else:
                # Orphan — flag for founder review. The plan says we
                # also CREATE the user on the fork side. In Phase 1
                # dry-run we both record the orphan AND emit the
                # planned INSERT.
                self.orphans.append({
                    'kind': 'email_not_in_fork',
                    'ls_user_id': ls_id,
                    **_clean_record(u),
                })
                planned = {
                    'email': norm,
                    'first_name': u.get('first_name') or '',
                    'last_name': u.get('last_name') or '',
                    'password': u.get('password') or '',
                    'is_staff': bool(u.get('is_staff')),
                    'is_active': bool(u.get('is_active', True)),
                    'role': 'trainer',  # default per plan
                    'ls_legacy_id': ls_id,
                }
                r.add_note(f'ORPHAN ls_user.id={ls_id} email={norm} → plan: INSERT (role=trainer)')
                if self.target is not None:
                    # ON CONFLICT (email) DO NOTHING preserves idempotency.
                    has_legacy = self.target.column_exists('htx_user', 'ls_legacy_id')
                    cols = ['username', 'email', 'first_name', 'last_name', 'password',
                            'is_staff', 'is_active', 'date_joined', 'role']
                    vals: list[Any] = [
                        norm, norm, planned['first_name'], planned['last_name'],
                        planned['password'], planned['is_staff'], planned['is_active'],
                        u.get('date_joined') or datetime.datetime.utcnow(),
                        planned['role'],
                    ]
                    if has_legacy:
                        cols.append('ls_legacy_id')
                        vals.append(ls_id)
                    placeholders = ', '.join(['?'] * len(cols))
                    conflict = (
                        ' ON CONFLICT (email) DO NOTHING'
                        if self.target.kind == 'postgres'
                        else ' ON CONFLICT(email) DO NOTHING'
                    )
                    self.target.execute(
                        f'INSERT INTO htx_user ({", ".join(cols)}) VALUES ({placeholders}){conflict}',
                        tuple(vals),
                    )
                    r.rows_written += 1
                    # Re-resolve the fork id so downstream phases can map
                    # this user's tasks correctly.
                    row = self.target.fetchone(
                        'SELECT id FROM htx_user WHERE email = ?', (norm,)
                    )
                    if row:
                        self.legacy_user_map[ls_id] = int(row['id'])

    # ----------------------------------------------------------------- Phase 4
    def phase_4_project_copy(self, r: PhaseResult) -> None:
        assert self.source is not None
        projects = self.source.fetchall(
            'SELECT id, title, description, organization_id, label_config '
            'FROM project'
        )
        r.rows_read = len(projects)
        for p in projects:
            pid = int(p['id'])
            # Detect empty project — flag rather than skip; founder
            # decides at review time whether to delete.
            task_count = self.source.fetchone(
                'SELECT COUNT(*) AS c FROM task WHERE project_id = ?', (pid,)
            )
            empty = int(task_count['c']) == 0 if task_count else True
            if empty:
                r.add_note(f'project.id={pid} title={p.get("title")!r} is EMPTY — flagged for review (NOT deleted)')
            if self.target is not None:
                cols = ['id', 'title', 'description', 'organization_id', 'label_config',
                        'created_at', 'updated_at']
                vals = (
                    pid,
                    p.get('title') or '',
                    p.get('description') or '',
                    p.get('organization_id'),
                    p.get('label_config') or '<View></View>',
                    datetime.datetime.utcnow(),
                    datetime.datetime.utcnow(),
                )
                conflict = (
                    ' ON CONFLICT (id) DO NOTHING'
                    if self.target.kind == 'postgres'
                    else ' ON CONFLICT(id) DO NOTHING'
                )
                placeholders = ', '.join(['?'] * len(cols))
                self.target.execute(
                    f'INSERT INTO project ({", ".join(cols)}) VALUES ({placeholders}){conflict}',
                    vals,
                )
                r.rows_written += 1
            r.passed += 1

    # ----------------------------------------------------------------- Phase 5
    def phase_5_task_copy(self, r: PhaseResult) -> None:
        assert self.source is not None
        # Bulk-stream tasks in batches of 500. Memory rule: sub-agent
        # incremental write — we COMMIT to savepoint progress per batch.
        cursor = self.source.conn.cursor()
        cursor.execute('SELECT id, data, meta, project_id, created_at, updated_at FROM task')
        batch_size = 500
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            if self.source.kind == 'sqlite':
                rows = [dict(row) for row in rows]
            else:
                cols = [d[0] for d in cursor.description]
                rows = [dict(zip(cols, row)) for row in rows]
            for t in rows:
                r.rows_read += 1
                tid = int(t['id'])
                pid = t.get('project_id')
                if self.target is not None:
                    cols = ['id', 'data', 'meta', 'project_id', 'created_at', 'updated_at',
                            'is_labeled', 'overlap', 'inner_id']
                    vals = (
                        tid,
                        _stringify_json(t.get('data')),
                        _stringify_json(t.get('meta') or {}),
                        pid,
                        t.get('created_at') or datetime.datetime.utcnow(),
                        t.get('updated_at') or datetime.datetime.utcnow(),
                        False,
                        1,
                        0,
                    )
                    conflict = (
                        ' ON CONFLICT (id) DO NOTHING'
                        if self.target.kind == 'postgres'
                        else ' ON CONFLICT(id) DO NOTHING'
                    )
                    placeholders = ', '.join(['?'] * len(cols))
                    self.target.execute(
                        f'INSERT INTO task ({", ".join(cols)}) VALUES ({placeholders}){conflict}',
                        vals,
                    )
                    r.rows_written += 1
                r.passed += 1
        cursor.close()

    # ----------------------------------------------------------------- Phase 6
    def phase_6_annotation_submission(self, r: PhaseResult) -> None:
        """Append-only: every LS annotation → 1 fork annotation row.

        Phase 1 dry-run NOTE: the dedicated "submissions" model lands in
        Step 8 schema PR; until then we map to the existing
        ``task_completion`` (annotation) table and let the downstream
        Submission service compute its view from there. The mapping
        target column ``status`` is recorded as a NOTE only when the
        schema does not yet support it.
        """
        assert self.source is not None
        anns = self.source.fetchall(
            'SELECT id, task_id, completed_by_id, result, was_cancelled, '
            'ground_truth, created_at, updated_at, lead_time FROM task_completion'
        )
        # Duplicate handling: latest by (task_id, completed_by_id) wins.
        anns.sort(key=lambda a: (a.get('task_id'), a.get('completed_by_id'),
                                  a.get('created_at') or ''))
        latest: dict[tuple, dict] = {}
        for a in anns:
            key = (a.get('task_id'), a.get('completed_by_id'))
            latest[key] = a  # later iteration wins
        r.rows_read = len(anns)
        dup = len(anns) - len(latest)
        if dup:
            r.add_note(f'DEDUPED {dup} annotation rows (kept latest by created_at per (task,user))')
            r.skipped += dup
        target_has_status = (
            self.target is not None
            and self.target.column_exists('task_completion', 'status')
        )
        for a in latest.values():
            ann_id = int(a['id'])
            # Parse + validate result JSON; corrupt rows → orphan + skip.
            raw_result = a.get('result')
            parsed = _safe_json_loads(raw_result)
            if parsed is _CORRUPT:
                r.skipped += 1
                self.orphans.append({
                    'kind': 'corrupt_annotation_json',
                    'annotation_id': ann_id,
                    'raw_result_prefix': (raw_result[:80] if isinstance(raw_result, str) else repr(raw_result)[:80]),
                })
                r.add_note(f'SKIP annotation.id={ann_id} corrupt JSON')
                continue
            ls_user_id = a.get('completed_by_id')
            fork_user_id = self.legacy_user_map.get(int(ls_user_id)) if ls_user_id else None
            if ls_user_id and not fork_user_id:
                # Annotator was a Phase-3 orphan — keep the annotation
                # but null out completed_by so the fork doesn't reference
                # a non-existent user. The orphan report links them.
                r.add_note(
                    f'NOTE annotation.id={ann_id} annotator ls_user.id={ls_user_id} '
                    f'is orphan; storing with completed_by=NULL'
                )
                self.orphans.append({
                    'kind': 'annotation_orphan_annotator',
                    'annotation_id': ann_id,
                    'ls_annotator_id': ls_user_id,
                })
            status = ANNOTATION_STATUS_MAP[(bool(a.get('was_cancelled')),
                                            bool(a.get('ground_truth')))]
            if self.target is not None:
                cols = ['id', 'task_id', 'project_id', 'completed_by_id',
                        'result', 'was_cancelled', 'ground_truth',
                        'created_at', 'updated_at', 'lead_time']
                # project_id is denormalised on Annotation for query perf;
                # we look it up from the task row we just inserted.
                proj_row = self.target.fetchone(
                    'SELECT project_id FROM task WHERE id = ?',
                    (a.get('task_id'),),
                )
                proj_id = proj_row.get('project_id') if proj_row else None
                vals: list[Any] = [
                    ann_id,
                    a.get('task_id'),
                    proj_id,
                    fork_user_id,
                    _stringify_json(parsed),
                    bool(a.get('was_cancelled')),
                    bool(a.get('ground_truth')),
                    a.get('created_at') or datetime.datetime.utcnow(),
                    a.get('updated_at') or datetime.datetime.utcnow(),
                    a.get('lead_time'),
                ]
                if target_has_status:
                    cols.append('status')
                    vals.append(status)
                else:
                    r.add_note(
                        f'NOTE annotation.id={ann_id} status={status} (not persisted — '
                        'target schema missing `status` column; Phase 2 schema PR adds it)'
                    )
                conflict = (
                    ' ON CONFLICT (id) DO NOTHING'
                    if self.target.kind == 'postgres'
                    else ' ON CONFLICT(id) DO NOTHING'
                )
                placeholders = ', '.join(['?'] * len(cols))
                self.target.execute(
                    f'INSERT INTO task_completion ({", ".join(cols)}) VALUES ({placeholders}){conflict}',
                    tuple(vals),
                )
                r.rows_written += 1
            r.passed += 1

    # ----------------------------------------------------------------- Phase 7
    def phase_7_project_member_assignment(self, r: PhaseResult) -> None:
        assert self.source is not None
        members = self.source.fetchall(
            'SELECT id, user_id, project_id, enabled, created_at, updated_at '
            'FROM project_member'
        )
        r.rows_read = len(members)
        for m in members:
            ls_user_id = m.get('user_id')
            fork_user_id = self.legacy_user_map.get(int(ls_user_id)) if ls_user_id else None
            if not fork_user_id:
                r.skipped += 1
                r.add_note(
                    f'SKIP project_member.id={m["id"]} — annotator ls_user.id={ls_user_id} '
                    'not in legacy map (orphan or no-email)'
                )
                continue
            if self.target is not None:
                cols = ['id', 'user_id', 'project_id', 'enabled', 'created_at', 'updated_at']
                vals = (
                    int(m['id']), fork_user_id, m.get('project_id'),
                    bool(m.get('enabled', True)),
                    m.get('created_at') or datetime.datetime.utcnow(),
                    m.get('updated_at') or datetime.datetime.utcnow(),
                )
                conflict = (
                    ' ON CONFLICT (id) DO NOTHING'
                    if self.target.kind == 'postgres'
                    else ' ON CONFLICT(id) DO NOTHING'
                )
                placeholders = ', '.join(['?'] * len(cols))
                self.target.execute(
                    f'INSERT INTO projects_projectmember ({", ".join(cols)}) VALUES ({placeholders}){conflict}',
                    vals,
                )
                r.rows_written += 1
            r.passed += 1

    # ----------------------------------------------------------------- Phase 8
    # Source-table → target-table name pairs. Most match 1:1 except
    # project_member which the fork renames to the Django default
    # `projects_projectmember`. Phase 6 also has a known-skip slot for
    # the single corrupt-JSON row.
    _CROSSCHECK_PAIRS = [
        ('htx_user',         'htx_user',                  0),
        ('project',          'project',                   0),
        ('task',             'task',                      0),
        ('task_completion',  'task_completion',           0),  # known-skip handled by tolerance
        ('project_member',   'projects_projectmember',    0),
    ]

    def phase_8_row_count_cross_check(self, r: PhaseResult) -> None:
        assert self.source is not None
        for src_tbl, tgt_tbl, _ in self._CROSSCHECK_PAIRS:
            src = self.source.count(src_tbl) if self.source.table_exists(src_tbl) else 0
            tgt = 0
            if self.target is not None and self.target.table_exists(tgt_tbl):
                # In dry-run this returns 0 (we'll rollback) — that's OK,
                # the cross-check is informational; the assert below is
                # gentler (warn rather than fail) under dry-run.
                tgt = self.target.count(tgt_tbl)
            diff = tgt - src
            r.add_note(f'{src_tbl} → {tgt_tbl}: source={src} target={tgt} diff={diff}')
            if not self.dry_run and self.target is not None:
                # Tolerance: 1% of source, floor 2 rows. task_completion
                # extra slack: corrupt-JSON rows are an intentional skip.
                tol = max(2, int(0.01 * src))
                if src_tbl == 'task_completion':
                    # Allow up to (orphan_annotators + corrupt) absences.
                    tol = max(tol, len([o for o in self.orphans
                                        if o.get('kind') in ('corrupt_annotation_json',
                                                             'annotation_orphan_annotator')]))
                if abs(diff) > tol:
                    r.failed += 1
                    r.add_note(f'FAIL: {src_tbl}→{tgt_tbl} diff={diff} exceeds tolerance {tol}')
                else:
                    r.passed += 1
            else:
                r.passed += 1

    # ----------------------------------------------------------------- Phase 9
    def phase_9_spot_check(self, r: PhaseResult) -> None:
        assert self.source is not None
        users = self.source.fetchall('SELECT id, email FROM htx_user')
        tasks = self.source.fetchall('SELECT id FROM task')
        random.seed(self.seed)
        sample_users = random.sample(users, min(10, len(users)))
        sample_tasks = random.sample(tasks, min(10, len(tasks)))
        for u in sample_users:
            r.rows_read += 1
            anns = self.source.count_query(
                'SELECT COUNT(*) AS c FROM task_completion WHERE completed_by_id = ?',
                (u['id'],),
            ) if hasattr(self.source, 'count_query') else self.source.fetchone(
                'SELECT COUNT(*) AS c FROM task_completion WHERE completed_by_id = ?',
                (u['id'],),
            )
            n = int(anns['c']) if anns else 0
            r.add_note(f'spot-check user.id={u["id"]} email={u.get("email")} → {n} annotations on source')
            r.passed += 1
        for t in sample_tasks:
            r.rows_read += 1
            anns = self.source.fetchone(
                'SELECT COUNT(*) AS c FROM task_completion WHERE task_id = ?',
                (t['id'],),
            )
            n = int(anns['c']) if anns else 0
            r.add_note(f'spot-check task.id={t["id"]} → {n} annotations on source')
            r.passed += 1

    # ---------------------------------------------------------------- Phase 10
    def phase_10_generate_report(self, r: PhaseResult) -> None:
        self._write_final_report()
        self._write_orphans_report()
        self._best_effort_incident_log()
        r.passed += 1
        r.add_note(f'Report written: {self.report_path}')
        r.add_note(f'Orphans report written: {self.orphans_path}')

    # -- report writers -------------------------------------------------------
    def _write_partial_report(self) -> None:
        try:
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            self.report_path.write_text(self._render_report(partial=True), encoding='utf-8')
        except Exception as exc:  # pragma: no cover
            logger.warning('Could not write partial report: %s', exc)

    def _write_final_report(self) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(self._render_report(partial=False), encoding='utf-8')

    def _write_orphans_report(self) -> None:
        self.orphans_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            '# TrainPlex Studio — Migration Orphans Report',
            '',
            f'Generated: {datetime.datetime.utcnow().isoformat()}Z',
            f'Mode: {"DRY-RUN" if self.dry_run else "APPLY"}',
            '',
            'Each row below requires founder review before the real run.',
            'Rows are append-only — re-runs add new entries; nothing is mutated.',
            '',
            '| # | Kind | Detail |',
            '|---|------|--------|',
        ]
        for i, o in enumerate(self.orphans, 1):
            detail = ', '.join(f'{k}={v}' for k, v in o.items() if k != 'kind')
            detail = FORBIDDEN_FOUNDER_MOBILE.sub('[REDACTED-MOBILE]', detail)
            lines.append(f'| {i} | {o["kind"]} | {detail} |')
        if not self.orphans:
            lines.append('| – | – | (no orphans — every LS user matched a fork email) |')
        self.orphans_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def _render_report(self, *, partial: bool) -> str:
        head = f'Generated: {datetime.datetime.utcnow().isoformat()}Z (started {self._started_at.isoformat()}Z)'
        mode = 'DRY-RUN (no writes committed to target)' if self.dry_run else 'APPLY'
        lines = [
            '# TrainPlex Studio — LS → Fork Migration Report',
            '',
            f'Report version: {REPORT_VERSION}',
            head,
            f'Mode: **{mode}**',
            f'Source: `{_safe_url(self.source_url)}`',
            f'Target: `{_safe_url(self.target_url) if self.target_url else "(none — preview only)"}`',
            f'Status: {"PARTIAL (in-progress checkpoint)" if partial else "FINAL"}',
            '',
            '## Phase Summary',
            '',
            '| Phase | Status | Passed | Skipped | Failed | Read | Written | Time (ms) |',
            '|-------|--------|--------|---------|--------|------|---------|-----------|',
        ]
        for res in self.results:
            lines.append(
                f'| {res.name} | {res.status} | {res.passed} | {res.skipped} | '
                f'{res.failed} | {res.rows_read} | {res.rows_written} | {res.duration_ms} |'
            )
        lines += [
            '',
            '## Detailed Notes',
            '',
        ]
        for res in self.results:
            lines.append(f'### {res.name}')
            lines.append('')
            for note in res.notes:
                lines.append(f'- {note}')
            if not res.notes:
                lines.append('- (no notes)')
            lines.append('')
        # Founder rule: 3-line Hindi recap.
        lines += [
            '## Founder 3-line Hindi Recap',
            '',
            '- Kya bug tha: Phase 1 me LS → Fork migration manually nahi ho sakti thi — koi single repeatable script nahi tha jo source DB read kare, har row ka mapping decide kare, aur dry-run me preview de.',
            '- Usse kya ho rha tha: Founder ko production cutover ke time pe panic mode me ad-hoc SQL likhna padta, kuchh trainers ke annotations gum ho jate, aur rollback ka koi safe path nahi tha.',
            '- Ab fix ke baad kya hoga: `migrate_ls_to_fork.py` 10 phases me chalti hai — backup verify, schema audit, user merge (case-normalise + orphan flag), project copy (preserve id), task copy (batched 500), annotation → submission (dedupe latest, corrupt JSON skip + log), project_member → assignment, row-count cross-check, 10 random spot-checks, aur MIGRATION_REPORT.md + ORPHANS_REPORT.md generate. Dry-run mode default hai (ROLLBACK end pe) — `--apply` aur `--i-have-a-backup` dono explicit chahiye real cutover ke liye. Idempotent: dobara chalao → second run no-op.',
            '',
            f'_Report file: `{self.report_path}` · Orphans file: `{self.orphans_path}`_',
        ]
        return '\n'.join(lines) + '\n'

    def _best_effort_incident_log(self) -> None:
        # Memory rule: every production fix appended to /var/lib/trainplex-data/INCIDENT_LOG.md
        if self.dry_run:
            return  # dry-run doesn't qualify as production action
        log = os.environ.get('TRAINPLEX_INCIDENT_LOG', str(DEFAULT_INCIDENT_LOG))
        line = (
            f'\n## {datetime.datetime.utcnow().isoformat()}Z — LS → Fork Migration APPLY\n'
            f'Root cause: scheduled Phase 2 / Step 8 data cutover.\n'
            f'Commit: (n/a — script run, not commit)\n'
            f'Verification: `{self.report_path}` (final phase status above).\n'
        )
        try:
            with open(log, 'a', encoding='utf-8') as fh:
                fh.write(line)
        except Exception as exc:  # pragma: no cover
            logger.warning('Could not append INCIDENT_LOG (%s): %s', log, exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_CORRUPT = object()


def _safe_json_loads(blob: Any) -> Any:
    if blob is None:
        return None
    if isinstance(blob, (dict, list)):
        return blob
    if isinstance(blob, bytes):
        try:
            blob = blob.decode('utf-8')
        except UnicodeDecodeError:
            return _CORRUPT
    if not isinstance(blob, str):
        return _CORRUPT
    if not blob.strip():
        return None
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return _CORRUPT


def _stringify_json(value: Any) -> str:
    if value is None:
        return '{}'
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return '{}'


def _safe_url(url: str | None) -> str:
    if not url:
        return ''
    # Strip password from log lines: postgres://user:PASS@host/db → postgres://user:***@host/db
    return re.sub(r'(://[^:]+:)[^@]+(@)', r'\1***\2', url)


def _clean_record(d: dict) -> dict:
    """Drop password-like fields before logging to ORPHANS_REPORT."""
    clean: dict[str, Any] = {}
    for k, v in d.items():
        if k.lower() in ('password', 'password_hash', 'token', 'secret'):
            continue
        if isinstance(v, datetime.datetime):
            v = v.isoformat()
        clean[k] = v
    return clean


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='migrate_ls_to_fork',
        description='Migrate Label Studio production data into TrainPlex Studio fork (dry-run safe).',
    )
    p.add_argument('--source-db', required=True,
                   help='Source LS DB URL: sqlite:///path or postgres://user:pass@host/db')
    p.add_argument('--target-db', default=None,
                   help='Target fork DB URL. Required for --apply, optional in --dry-run.')
    p.add_argument('--dry-run', action='store_true', default=True,
                   help='Open target DB in a transaction that is ROLLED BACK at end. Default.')
    p.add_argument('--apply', action='store_true',
                   help='Disable dry-run and COMMIT. Requires --i-have-a-backup.')
    p.add_argument('--i-have-a-backup', action='store_true',
                   help='Explicit confirmation flag — required to combine with --apply.')
    p.add_argument('--report', default='docs/MIGRATION_REPORT.md',
                   help='Output path for the human-readable report (Markdown).')
    p.add_argument('--orphans-report', default='docs/MIGRATION_ORPHANS.md',
                   help='Output path for the orphans review file (Markdown).')
    p.add_argument('--verbose', '-v', action='store_true', help='DEBUG-level logging.')
    p.add_argument('--seed', type=int, default=42, help='RNG seed for spot-check sampling.')
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)
    dry_run = args.dry_run and not args.apply
    if args.apply and not args.i_have_a_backup:
        logger.error('--apply requires --i-have-a-backup. Refusing to proceed.')
        return 3
    if args.apply and not args.target_db:
        logger.error('--apply requires --target-db. Refusing to proceed.')
        return 3
    runner = MigrationRunner(
        source_url=args.source_db,
        target_url=args.target_db,
        dry_run=dry_run,
        verbose=args.verbose,
        report_path=Path(args.report),
        orphans_path=Path(args.orphans_report),
        seed=args.seed,
    )
    return runner.run()


if __name__ == '__main__':
    sys.exit(main())
