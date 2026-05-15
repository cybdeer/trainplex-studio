"""
TrainPlex Studio — Migration Dry-Run Wrapper
============================================

One-shot convenience wrapper for the Phase 1 Step 8.5 dry-run gate.
Calls ``migrate_ls_to_fork.py --dry-run --verbose`` against the source
DB the founder pasted in, then prints the first few sections of the
generated MIGRATION_REPORT.md so the founder can eyeball the result
without leaving the terminal.

Usage
-----
    python migration_dry_run.py --source-db <url> [--target-db <url>]

Always exits with the inner script's exit code so CI can gate on it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from migrate_ls_to_fork import main as run_migration  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='Run the migration in dry-run mode and print the report preview.')
    p.add_argument('--source-db', required=True)
    p.add_argument('--target-db', default=None)
    p.add_argument('--report', default='docs/MIGRATION_REPORT.md')
    p.add_argument('--orphans-report', default='docs/MIGRATION_ORPHANS.md')
    p.add_argument('--seed', type=int, default=42)
    args = p.parse_args(argv)

    inner = [
        '--source-db', args.source_db,
        '--dry-run',
        '--verbose',
        '--report', args.report,
        '--orphans-report', args.orphans_report,
        '--seed', str(args.seed),
    ]
    if args.target_db:
        inner.extend(['--target-db', args.target_db])
    rc = run_migration(inner)

    report = Path(args.report)
    if report.exists():
        text = report.read_text(encoding='utf-8')
        # Print the first ~80 lines or up to the "Founder 3-line Hindi Recap" section.
        lines = text.splitlines()
        preview = []
        for line in lines:
            preview.append(line)
            if line.startswith('## Founder 3-line Hindi Recap'):
                preview.append('... (recap omitted from preview; see full report) ...')
                break
            if len(preview) > 120:
                preview.append('... (truncated; see full report) ...')
                break
        sys.stdout.write('\n--- MIGRATION_REPORT.md preview ---\n')
        sys.stdout.write('\n'.join(preview) + '\n')
        sys.stdout.write(f'--- end preview (full report: {report}) ---\n')
    return rc


if __name__ == '__main__':
    sys.exit(main())
