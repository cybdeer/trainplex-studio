# LS → Fork Migration Playbook

Phase 1 Step 8 timeline + commands. Founder reads this top-to-bottom before
the production cutover; every step has a command, an expected output, and
a founder approval gate before moving on.

The script that backs every step is `backend/scripts/migrate_ls_to_fork.py`.
Tests live at `label_studio/tests/test_migration_script.py` (9 tests).

---

## T−7 days — Rehearsal kickoff

| # | Action | Command | Expected | Gate |
|---|--------|---------|----------|------|
| 1 | Snapshot LS prod DB | `pg_dump -Fc -h LS_HOST -U LS_USER labelstudio > /backups/ls-T7.dump` | dump file ≥ live DB size | Founder ack |
| 2 | Bring snapshot into a sandbox | `pg_restore -d ls_snapshot /backups/ls-T7.dump` | psql `\dt` lists `htx_user`, `project`, `task`, `task_completion`, `project_member` | — |
| 3 | Provision a fork sandbox DB | `createdb trainplex_sandbox` + run fork migrations | `manage.py migrate` exits 0 | — |
| 4 | Dry-run against the snapshot | see "Dry-Run Command" below | Phase Summary: all phases `OK`, `task_completion` skipped count == corrupt-JSON count + orphan-annotator count | Founder reviews `MIGRATION_REPORT.md` |
| 5 | Founder reviews `MIGRATION_ORPHANS.md` | open file in editor | every orphan row is either: (a) a real lapsed trainer (mark "create"), or (b) test/dev account (mark "skip") | Founder ack |

### Dry-Run Command

```bash
python backend/scripts/migration_dry_run.py \
    --source-db postgres://LS_USER:LS_PASS@LS_HOST:5432/ls_snapshot \
    --target-db postgres://FORK_USER:FORK_PASS@FORK_HOST:5432/trainplex_sandbox \
    --report docs/MIGRATION_REPORT.md \
    --orphans-report docs/MIGRATION_ORPHANS.md
```

The dry-run wrapper invokes `migrate_ls_to_fork.py --dry-run --verbose` and
prints the first ~120 lines of the report to stdout so the founder can
eyeball it immediately.

Exit codes:
- `0` — every phase passed (Phase 8 cross-check within tolerance)
- `2` — at least one phase failed; do NOT proceed to cutover
- `3` — argument error (e.g. missing `--source-db`)

---

## T−3 days — Sandbox reality check

| # | Action | Command | Expected | Gate |
|---|--------|---------|----------|------|
| 1 | Real apply on sandbox | swap `--dry-run` for `--apply --i-have-a-backup` | Phase 8 PASS, exit code 0 | — |
| 2 | Run verification | `python backend/scripts/verify_migration.py --source-db <sandbox-ls> --target-db <sandbox-fork>` | `VERIFICATION_REPORT.md` reports zero mapping problems and zero spot-check failures | Founder ack |
| 3 | Smoke test fork UI | login as 5 random trainers, view their full task history | every page renders, annotations match LS counts | Founder ack |

If step 3 fails for any trainer: stop, file an orphan-resolution decision in
the orphans report, redo from T-7. **Never** proceed to T-0 without all
three gates green.

---

## T−1 day — Production approval

| # | Action | Command | Expected | Gate |
|---|--------|---------|----------|------|
| 1 | Final dry-run against **live** LS prod DB | `migration_dry_run.py` with prod URL | identical report to T-7 (drift ≤ 1%) | Founder ack |
| 2 | Communicate maintenance window | WA broadcast + email | trainers acknowledge | — |
| 3 | Confirm LS container snapshot exists | `docker ps -a | grep labelstudio` | container present + last backup ≤ 24h | — |

---

## T−0 — Cutover (60-minute window)

1. **00:00** — Pause LS writes (read-only mode via env var on LS app).
2. **00:05** — Take final hot backup: `pg_dump -Fc … > /backups/ls-final.dump`.
3. **00:10** — Run real apply:

   ```bash
   python backend/scripts/migrate_ls_to_fork.py \
       --source-db postgres://LS_USER:LS_PASS@LS_HOST:5432/labelstudio \
       --target-db postgres://FORK_USER:FORK_PASS@FORK_HOST:5432/trainplex \
       --apply --i-have-a-backup --verbose \
       --report docs/MIGRATION_REPORT.md \
       --orphans-report docs/MIGRATION_ORPHANS.md
   ```

   Expected: exit code `0`, `Phase 8` PASS, `task_completion` diff
   within tolerance.

4. **00:30** — Run `verify_migration.py` (read-only on both DBs).
5. **00:45** — Smoke test 3 trainers (login + task list + 1 annotation).
6. **00:55** — Flip nginx routing to fork upstream.
7. **01:00** — Founder posts "live" in WA broadcast.

### Approval Gates

| Gate | Held by | Pass condition |
|------|---------|----------------|
| T−7 dry-run report | Founder | Phase summary all OK, orphans triaged |
| T−3 sandbox apply | Founder | verify_migration exit 0, 5 trainer smoke OK |
| T−1 prod dry-run | Founder | drift vs T-7 ≤ 1% |
| T−0 minute 45 smoke | Founder | 3 trainers view full history |

---

## T+1 day — Post-cutover

- Hourly cron: `verify_migration.py --samples 50` for 24h. Any failure →
  alert founder via WA webhook; do NOT auto-rollback (operator-only).
- `INCIDENT_LOG.md` appended automatically by the migration script on
  `--apply` runs.

---

## T+30 days — Decommission LS

- Confirm zero verification failures across the 30-day window.
- Founder approval gate (last one): archive LS container image, snapshot
  final DB to cold storage, then `docker rm`.

If at any point in the 30-day window something looks wrong, see
[ROLLBACK_PROCEDURE.md](ROLLBACK_PROCEDURE.md).

---

## Founder rule recap

- The script never embeds the founder's personal mobile in any output
  (a regex built from `TRAINPLEX_FOUNDER_MOBILE_GUARD` strips the
  `<configured-guard>` digits from every note before write).
- Every `--apply` run appends a row to
  `/var/lib/trainplex-data/INCIDENT_LOG.md` so recurrences are traceable.
- The script is idempotent (`ON CONFLICT DO NOTHING` everywhere) — a
  second `--apply` after a partial failure is safe.
