"""
TrainPlex Studio — Post-migration audit
=======================================

Run AFTER ``migrate_ls_to_fork.py --apply`` has committed. The script
re-opens BOTH DBs read-only, recounts every relevant table, validates
the ls_legacy_id linkage, and spot-checks 20 random users + tasks for
data fidelity. Output: VERIFICATION_REPORT.md.

Verification is read-only on BOTH databases.

Usage
-----
    python verify_migration.py \\
        --source-db postgres://USER:PASS@host:5432/labelstudio \\
        --target-db postgres://USER:PASS@host:5432/trainplex \\
        [--seed 42] \\
        [--samples 20] \\
        [--report docs/VERIFICATION_REPORT.md] \\
        [--verbose]

Exit codes
----------
* ``0`` — counts match within tolerance; spot-checks all OK
* ``1`` — argument error
* ``2`` — counts differ above tolerance, or a spot-check sample
  could not be located on the target side

The verifier never modifies either DB.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import random
import sys
from pathlib import Path

# Reuse the DB wrapper + helpers from the migration script so the two
# stay schema-consistent.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from migrate_ls_to_fork import (  # noqa: E402  (deliberate import-after-sys-path)
    DBHandle, REQUIRED_SOURCE_TABLES, setup_logging, _safe_url,
)

logger = logging.getLogger('verify_migration')


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='verify_migration', description=__doc__)
    p.add_argument('--source-db', required=True)
    p.add_argument('--target-db', required=True)
    p.add_argument('--samples', type=int, default=20)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--report', default='docs/VERIFICATION_REPORT.md')
    p.add_argument('--verbose', '-v', action='store_true')
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)
    src = DBHandle.open(args.source_db, read_only=True)
    tgt = DBHandle.open(args.target_db, read_only=True)
    random.seed(args.seed)

    diffs: list[dict] = []
    for tbl in REQUIRED_SOURCE_TABLES:
        s = src.count(tbl) if src.table_exists(tbl) else 0
        t = tgt.count(tbl) if tgt.table_exists(tbl) else 0
        diffs.append({'table': tbl, 'source': s, 'target': t, 'diff': t - s})
        logger.info('count %s: source=%s target=%s diff=%s', tbl, s, t, t - s)

    # Validate legacy mapping
    mapping_problems = 0
    if tgt.column_exists('htx_user', 'ls_legacy_id'):
        rows = tgt.fetchall(
            'SELECT id, email, ls_legacy_id FROM htx_user WHERE ls_legacy_id IS NOT NULL'
        )
        ls_ids = {int(r['ls_legacy_id']) for r in rows}
        for ls_id in ls_ids:
            row = src.fetchone('SELECT 1 FROM htx_user WHERE id = ?', (ls_id,))
            if not row:
                mapping_problems += 1
                logger.warning('ls_legacy_id=%s present on target but missing on source', ls_id)

    # Spot-check users
    users = src.fetchall('SELECT id, email FROM htx_user')
    sample_users = random.sample(users, min(args.samples, len(users)))
    spot_check_failures = 0
    spot_check_notes: list[str] = []
    for u in sample_users:
        norm = (u.get('email') or '').strip().lower()
        if not norm:
            continue
        row = tgt.fetchone('SELECT id FROM htx_user WHERE LOWER(email) = ?', (norm,))
        if not row:
            spot_check_failures += 1
            spot_check_notes.append(f'MISSING ON TARGET: ls_user.id={u["id"]} email={norm}')
        else:
            spot_check_notes.append(f'OK ls_user.id={u["id"]} → fork.id={row["id"]} ({norm})')

    # Spot-check tasks
    tasks = src.fetchall('SELECT id FROM task')
    sample_tasks = random.sample(tasks, min(args.samples, len(tasks)))
    for t in sample_tasks:
        row = tgt.fetchone('SELECT id FROM task WHERE id = ?', (t['id'],))
        if not row:
            spot_check_failures += 1
            spot_check_notes.append(f'MISSING ON TARGET: task.id={t["id"]}')
        else:
            spot_check_notes.append(f'OK task.id={t["id"]}')

    # Build report
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    lines = [
        '# TrainPlex Studio — Post-Migration Verification Report',
        '',
        f'Generated: {datetime.datetime.utcnow().isoformat()}Z',
        f'Source: `{_safe_url(args.source_db)}`',
        f'Target: `{_safe_url(args.target_db)}`',
        f'Samples per table: {args.samples}',
        '',
        '## Row Count Cross-Check',
        '',
        '| Table | Source | Target | Diff |',
        '|-------|--------|--------|------|',
    ]
    for d in diffs:
        lines.append(f'| {d["table"]} | {d["source"]} | {d["target"]} | {d["diff"]} |')
    lines += [
        '',
        '## ls_legacy_id Mapping',
        '',
        f'Mapping problems (legacy id present on target but absent on source): **{mapping_problems}**',
        '',
        '## Spot Checks',
        '',
        f'Failures: **{spot_check_failures}** out of {len(sample_users) + len(sample_tasks)} samples.',
        '',
    ]
    for n in spot_check_notes:
        lines.append(f'- {n}')
    Path(args.report).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    logger.info('Verification report: %s', args.report)

    src.close()
    tgt.close()
    rc = 0
    if spot_check_failures or mapping_problems or any(abs(d['diff']) > max(2, int(0.01 * d['source'])) for d in diffs):
        rc = 2
    return rc


if __name__ == '__main__':
    sys.exit(main())
