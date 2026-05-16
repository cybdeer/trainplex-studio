"""
Tests for backend/scripts/migrate_ls_to_fork.py (Phase 1 Step 8.5).

These tests are intentionally Django-independent. The migration script
runs OUTSIDE the Django stack (it is invoked during the production
cutover before the fork container's wsgi has even booted) so the tests
mirror that environment: they build two on-disk SQLite databases with
the relevant subset of the LS / fork schemas, drive the script against
them, and assert on its side-effects (the MIGRATION_REPORT.md and
ORPHANS_REPORT.md files).

Test plan (matches the deliverable in the Step 8.5 brief):
  1. fixture_loads — source schema with 5 users, 3 projects, 10 tasks,
     8 annotations bootstraps cleanly.
  2. dry_run_writes_nothing — dry-run run on a fresh target DB does not
     mutate it (row counts unchanged).
  3. real_run_counts_match — --apply mode lands the expected number of
     rows in every target table.
  4. idempotent — running --apply twice is a no-op the second time.
  5. orphan_user_creates_report_entry — LS user whose email is not in
     fork is recorded in the orphans report.
  6. corrupt_annotation_json_logged — annotation row with malformed
     JSON shows up in the orphans report with kind=corrupt_annotation_json.
  7. email_case_mismatch_normalized — `Foo@x.com` (LS) ↔ `foo@x.com`
     (fork) → MATCH (case-folded).
  8. founder_mobile_redacted — if any LS row contains the founder mobile
     in a freeform field, it must NOT appear in any report.

The tests purposefully do NOT import Django settings and do NOT require
the dev container. Run via pytest directly:

    pytest label_studio/tests/test_migration_script.py -v
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

import pytest

# Sentinel mobile used only to plant a synthetic "leak" in test data.
# The real founder mobile lives in `.env` (gitignored) and is loaded at
# runtime by the migration script; this file never embeds the real value.
_TEST_SENTINEL_MOBILE = '9876543210'


def _resolve_founder_mobile() -> str:
    raw = os.environ.get('TRAINPLEX_FOUNDER_MOBILE_GUARD', '').strip()
    digits = re.sub(r'\D+', '', raw)
    if len(digits) >= 10:
        return digits[-10:]
    return _TEST_SENTINEL_MOBILE


_FOUNDER_MOBILE_FOR_TEST = _resolve_founder_mobile()

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / 'backend' / 'scripts'
sys.path.insert(0, str(SCRIPT_DIR))

from migrate_ls_to_fork import main as migration_main  # noqa: E402


# ---------------------------------------------------------------------------
# Schema fixtures — tiny replicas of the LS source + fork target shapes.
# The fork schema mirrors the parts of django models the script touches.
# ---------------------------------------------------------------------------
SOURCE_SCHEMA = """
CREATE TABLE htx_user (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE,
    password TEXT,
    first_name TEXT,
    last_name TEXT,
    is_staff BOOLEAN DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    date_joined TEXT
);
CREATE TABLE project (
    id INTEGER PRIMARY KEY,
    title TEXT,
    description TEXT,
    organization_id INTEGER,
    label_config TEXT
);
CREATE TABLE task (
    id INTEGER PRIMARY KEY,
    data TEXT,
    meta TEXT,
    project_id INTEGER,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE task_completion (
    id INTEGER PRIMARY KEY,
    task_id INTEGER,
    completed_by_id INTEGER,
    result TEXT,
    was_cancelled BOOLEAN DEFAULT 0,
    ground_truth BOOLEAN DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    lead_time REAL
);
CREATE TABLE project_member (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    project_id INTEGER,
    enabled BOOLEAN DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);
"""

FORK_SCHEMA = """
CREATE TABLE htx_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT UNIQUE,
    password TEXT,
    first_name TEXT DEFAULT '',
    last_name TEXT DEFAULT '',
    is_staff BOOLEAN DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    date_joined TEXT,
    role TEXT DEFAULT 'trainer',
    ls_legacy_id INTEGER
);
CREATE TABLE project (
    id INTEGER PRIMARY KEY,
    title TEXT,
    description TEXT,
    organization_id INTEGER,
    label_config TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE task (
    id INTEGER PRIMARY KEY,
    data TEXT,
    meta TEXT,
    project_id INTEGER,
    created_at TEXT,
    updated_at TEXT,
    is_labeled BOOLEAN DEFAULT 0,
    overlap INTEGER DEFAULT 1,
    inner_id INTEGER DEFAULT 0
);
CREATE TABLE task_completion (
    id INTEGER PRIMARY KEY,
    task_id INTEGER,
    project_id INTEGER,
    completed_by_id INTEGER,
    result TEXT,
    was_cancelled BOOLEAN DEFAULT 0,
    ground_truth BOOLEAN DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    lead_time REAL,
    status TEXT
);
CREATE TABLE projects_projectmember (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    project_id INTEGER,
    enabled BOOLEAN DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);
"""


def _bootstrap_source(path: Path, *, founder_mobile_in_notes: bool = False,
                     corrupt_one_json: bool = True,
                     mixed_case_email: bool = True) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(SOURCE_SCHEMA)
    now = datetime.datetime.utcnow().isoformat()
    cur = conn.cursor()
    # 5 users — the 4th has mixed-case email so we can test normalisation.
    emails = ['alice@example.com', 'BOB@example.com', 'carol@example.com',
              'Dave@Example.com' if mixed_case_email else 'dave@example.com',
              'eve@example.com']
    for i, email in enumerate(emails, 1):
        cur.execute(
            'INSERT INTO htx_user (id, email, password, first_name, last_name, '
            'is_staff, is_active, date_joined) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (i, email, 'pbkdf2_sha256$dummy', f'F{i}', f'L{i}', 0, 1, now),
        )
    # 3 projects, one empty.
    for pid in (1, 2, 3):
        title = f'Project {pid}'
        if pid == 3 and founder_mobile_in_notes:
            from core.services.founder_guard import get_guard_digits_no_cc
            mobile = get_guard_digits_no_cc()
            title = f'Project 3 mobile +91 {mobile} sneaks in here' if mobile else 'Project 3'
        cur.execute(
            'INSERT INTO project (id, title, description, organization_id, label_config) '
            'VALUES (?, ?, ?, ?, ?)',
            (pid, title, 'desc', 1, '<View></View>'),
        )
    # 10 tasks across projects 1 + 2 only (project 3 stays empty).
    for tid in range(1, 11):
        pid = 1 if tid <= 6 else 2
        cur.execute(
            'INSERT INTO task (id, data, meta, project_id, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (tid, json.dumps({'text': f'sample {tid}'}), '{}', pid, now, now),
        )
    # 8 annotations: 1 cancelled, 1 ground-truth, 1 corrupt JSON, rest normal.
    payloads = [
        (1, 1, '[{"from":"l","to":"t","value":"A"}]', 0, 0),
        (2, 2, '[{"from":"l","to":"t","value":"B"}]', 0, 0),
        (3, 3, '[{"from":"l","to":"t","value":"C"}]', 1, 0),  # cancelled
        (4, 4, '[{"from":"l","to":"t","value":"D"}]', 0, 1),  # ground truth
        (5, 5, '[{"from":"l","to":"t","value":"E"}]', 0, 0),
        (6, 1, '[{"from":"l","to":"t","value":"F"}]', 0, 0),
        (7, 2, '{not valid json' if corrupt_one_json else '[]', 0, 0),  # corrupt
        (8, 3, '[{"from":"l","to":"t","value":"H"}]', 0, 0),
    ]
    for i, (tid, uid, result, was_c, gt) in enumerate(payloads, 1):
        cur.execute(
            'INSERT INTO task_completion (id, task_id, completed_by_id, result, '
            'was_cancelled, ground_truth, created_at, updated_at, lead_time) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (i, tid, uid, result, was_c, gt, now, now, 1.5),
        )
    # 3 project_member rows.
    for (pmid, uid, pid) in [(1, 1, 1), (2, 2, 1), (3, 3, 2)]:
        cur.execute(
            'INSERT INTO project_member (id, user_id, project_id, enabled, '
            'created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
            (pmid, uid, pid, 1, now, now),
        )
    conn.commit()
    conn.close()


def _bootstrap_target(path: Path, *, prefill_emails: list[str] | None = None) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(FORK_SCHEMA)
    if prefill_emails:
        cur = conn.cursor()
        for email in prefill_emails:
            cur.execute(
                'INSERT INTO htx_user (username, email, password, role, is_active, date_joined) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (email, email, 'fork-pw', 'trainer', 1, datetime.datetime.utcnow().isoformat()),
            )
    conn.commit()
    conn.close()


def _count(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def _run(source: Path, target: Path | None, tmp: Path, *, apply: bool = False,
         extra: list[str] | None = None) -> tuple[int, Path, Path]:
    report = tmp / 'report.md'
    orphans = tmp / 'orphans.md'
    argv = [
        '--source-db', f'sqlite:///{source}',
        '--report', str(report),
        '--orphans-report', str(orphans),
        '--seed', '7',
    ]
    if target is not None:
        argv += ['--target-db', f'sqlite:///{target}']
    if apply:
        argv += ['--apply', '--i-have-a-backup']
    else:
        argv += ['--dry-run']
    if extra:
        argv += extra
    rc = migration_main(argv)
    return rc, report, orphans


@pytest.fixture()
def source_db(tmp_path: Path) -> Path:
    p = tmp_path / 'ls.sqlite3'
    _bootstrap_source(p)
    return p


@pytest.fixture()
def target_db(tmp_path: Path) -> Path:
    p = tmp_path / 'fork.sqlite3'
    # Pre-populate alice + carol so 3 will match and 2 (bob, dave, eve) are orphans.
    _bootstrap_target(p, prefill_emails=['alice@example.com', 'carol@example.com'])
    return p


def test_fixture_loads(source_db: Path):
    assert _count(source_db, 'htx_user') == 5
    assert _count(source_db, 'project') == 3
    assert _count(source_db, 'task') == 10
    assert _count(source_db, 'task_completion') == 8
    assert _count(source_db, 'project_member') == 3


def test_dry_run_writes_nothing(source_db: Path, target_db: Path, tmp_path: Path):
    before_users = _count(target_db, 'htx_user')
    before_projects = _count(target_db, 'project')
    before_tasks = _count(target_db, 'task')
    rc, report, _ = _run(source_db, target_db, tmp_path, apply=False)
    assert rc == 0
    # Dry-run rolled back: counts unchanged.
    assert _count(target_db, 'htx_user') == before_users
    assert _count(target_db, 'project') == before_projects
    assert _count(target_db, 'task') == before_tasks
    text = report.read_text(encoding='utf-8')
    assert 'DRY-RUN' in text
    assert '1_backup_verify' in text


def test_real_run_counts_match(source_db: Path, target_db: Path, tmp_path: Path):
    rc, report, _ = _run(source_db, target_db, tmp_path, apply=True)
    assert rc == 0, report.read_text(encoding='utf-8')
    # 2 pre-existing fork users + 3 orphans (bob, dave, eve) inserted = 5 total.
    assert _count(target_db, 'htx_user') == 5
    assert _count(target_db, 'project') == 3
    assert _count(target_db, 'task') == 10
    # 8 source annotations - 1 corrupt = 7 successfully inserted.
    assert _count(target_db, 'task_completion') == 7
    # 3 project_member rows all map (users 1,2,3 are all valid via mapping).
    assert _count(target_db, 'projects_projectmember') == 3


def test_idempotent(source_db: Path, target_db: Path, tmp_path: Path):
    rc1, report1, _ = _run(source_db, target_db, tmp_path, apply=True)
    assert rc1 == 0
    snapshot = {
        t: _count(target_db, t)
        for t in ('htx_user', 'project', 'task', 'task_completion', 'projects_projectmember')
    }
    rc2, report2, _ = _run(source_db, target_db, tmp_path, apply=True)
    assert rc2 == 0
    for t, n in snapshot.items():
        assert _count(target_db, t) == n, f'Idempotency broken on {t}'


def test_orphan_user_creates_report_entry(source_db: Path, target_db: Path, tmp_path: Path):
    rc, report, orphans = _run(source_db, target_db, tmp_path, apply=False)
    assert rc == 0
    o = orphans.read_text(encoding='utf-8')
    # bob, dave, eve have no fork-side match.
    assert 'email_not_in_fork' in o
    assert 'bob@example.com' in o.lower()


def test_corrupt_annotation_json_logged(source_db: Path, target_db: Path, tmp_path: Path):
    rc, report, orphans = _run(source_db, target_db, tmp_path, apply=False)
    assert rc == 0
    o = orphans.read_text(encoding='utf-8')
    assert 'corrupt_annotation_json' in o


def test_email_case_mismatch_normalized(tmp_path: Path):
    src = tmp_path / 'src.sqlite3'
    tgt = tmp_path / 'tgt.sqlite3'
    _bootstrap_source(src, mixed_case_email=True)
    # Fork has lower-case dave@example.com pre-existing.
    _bootstrap_target(tgt, prefill_emails=['dave@example.com'])
    rc, report, orphans = _run(src, tgt, tmp_path, apply=True)
    assert rc == 0, report.read_text(encoding='utf-8')
    # ls_legacy_id should be set on dave's row (LS user id=4 per fixture).
    conn = sqlite3.connect(tgt)
    try:
        row = conn.execute(
            'SELECT ls_legacy_id FROM htx_user WHERE LOWER(email) = ?',
            ('dave@example.com',),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == 4


def test_founder_mobile_redacted(tmp_path: Path):
    src = tmp_path / 'src.sqlite3'
    tgt = tmp_path / 'tgt.sqlite3'
    _bootstrap_source(src, founder_mobile_in_notes=True)
    _bootstrap_target(tgt)
    rc, report, orphans = _run(src, tgt, tmp_path, apply=False)
    assert rc == 0
    full = report.read_text(encoding='utf-8') + orphans.read_text(encoding='utf-8')
    # The literal must NOT appear anywhere in reports.
    from core.services.founder_guard import get_guard_digits_no_cc
    guard_digits = get_guard_digits_no_cc()
    if guard_digits:
        assert guard_digits not in full, 'Founder mobile leaked into a report'


def test_apply_without_backup_flag_refused(source_db: Path, target_db: Path, tmp_path: Path):
    rc, _, _ = _run(source_db, target_db, tmp_path, apply=False,
                    extra=['--apply'])  # missing --i-have-a-backup
    assert rc != 0  # script refuses
