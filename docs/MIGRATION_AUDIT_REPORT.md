# Migration Audit Report — Template (for founder review)

This file is the **template** the founder reads after every dry-run.
The migration script writes the live report to `docs/MIGRATION_REPORT.md`
(configurable via `--report`); this template documents what each
section means and what acceptance criteria look like.

If the live report has phases marked `FAILED`, **do not approve cutover**
— file an orphan-resolution decision and rerun the dry-run.

---

## Section 1 — Header

```
# TrainPlex Studio — LS → Fork Migration Report

Report version: 1.0
Generated: 2026-05-15T16:30:00.000000Z (started 2026-05-15T16:29:55.000000Z)
Mode: **DRY-RUN (no writes committed to target)**
Source: `postgres://ls_user:***@ls-host:5432/labelstudio`
Target: `postgres://fork_user:***@fork-host:5432/trainplex_sandbox`
Status: FINAL
```

Acceptance:
- `Mode` must read `DRY-RUN` at T-7 / T-1; `APPLY` only at T-0.
- Passwords MUST be redacted to `***` in both URLs (the script applies
  this scrub at log/report time).

---

## Section 2 — Phase Summary table

```
| Phase | Status | Passed | Skipped | Failed | Read | Written | Time (ms) |
|-------|--------|--------|---------|--------|------|---------|-----------|
| 1_backup_verify          | OK     | 5  | 0 | 0 | 1218 | 0  | 12   |
| 2_schema_audit           | OK     | 5  | 0 | 0 | 0    | 0  | 4    |
| 3_user_merge             | OK     | 17 | 0 | 0 | 17   | 17 | 38   |
| 4_project_copy           | OK     | 5  | 0 | 0 | 5    | 5  | 9    |
| 5_task_copy              | OK     | 1201 | 0 | 0 | 1201 | 1201 | 320 |
| 6_annotation_submission  | OK     | 940 | 5 | 0 | 945 | 940 | 280 |
| 7_project_member_assignment | OK  | 24 | 0 | 0 | 24   | 24 | 12   |
| 8_row_count_cross_check  | OK     | 5  | 0 | 0 | 0    | 0  | 6    |
| 9_spot_check             | OK     | 20 | 0 | 0 | 20   | 0  | 14   |
| 10_generate_report       | OK     | 1  | 0 | 0 | 0    | 0  | 8    |
```

Acceptance:
- All `Status` cells = `OK`.
- `Failed` column entirely zeros.
- `Skipped` non-zero only on `6_annotation_submission` (corrupt-JSON
  rows from LS — every entry must appear in `MIGRATION_ORPHANS.md`).
- Time per phase reasonable — `5_task_copy` ≥ 50ms per 1000 tasks is
  the rough operating envelope.

---

## Section 3 — Detailed Notes per phase

Each phase's notes block is a chronological audit trail. The founder
scans for:

- `WARN` / `FAIL` strings → escalate.
- `ORPHAN ls_user.id=...` → match against `MIGRATION_ORPHANS.md`.
- `SKIP annotation.id=... corrupt JSON` → confirm count == orphans file
  count of `kind: corrupt_annotation_json`.
- `NOTE annotation.id=... status=...` → expected in Phase 1 dry-runs
  while the `status` column has not landed on the target schema yet.
- `MATCH ls_user.id=... ↔ fork_user.id=...` → only present in
  `--verbose` mode (DEBUG-level log).

---

## Section 4 — Founder 3-line Hindi Recap

This is the founder-facing summary auto-appended to the bottom of every
report. The wording is fixed in `MigrationRunner._render_report` so
every run produces the same Hindi recap with only the file paths
changing — easy to compare run-over-run without reading the whole
report.

---

## How the founder uses this template

1. Run `migration_dry_run.py` (see [MIGRATION_PLAYBOOK.md](MIGRATION_PLAYBOOK.md)).
2. Open `docs/MIGRATION_REPORT.md`.
3. Confirm the Phase Summary matches the acceptance shape above.
4. Open `docs/MIGRATION_ORPHANS.md`.
5. For each orphan: decide "create with email/password as-is", "create
   with new email", or "skip permanently".
6. If approved, re-run with `--apply --i-have-a-backup`.
7. Otherwise, fix the LS data + re-run dry-run.

Founder approval gate is captured in the [Playbook](MIGRATION_PLAYBOOK.md)
table; this file is just the audit-report explainer.
