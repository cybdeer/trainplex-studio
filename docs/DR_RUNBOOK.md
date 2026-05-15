# TrainPlex Studio — Disaster Recovery Runbook

**Owner:** Founder + Claude (co-on-call).

**Scope:** what to do when production is hard-down or the DB is corrupted.
Smaller incidents (1 app server down, slow query, etc.) live in
`docs/INCIDENT_RESPONSE.md`.

---

## Targets

| Metric | Target | Why |
|--------|--------|-----|
| **RTO** (Recovery Time Objective) | ≤ 60 minutes from "platform down" → fully restored | One full hour of trainer work is the longest pause the founder will accept; longer and trust evaporates. |
| **RPO** (Recovery Point Objective) | ≤ 24 hours of data loss | We back up nightly. Hourly WAL shipping is a Step-17 Phase-2 upgrade. |
| **MTTR** (Mean Time To Repair) | ≤ 15 minutes for known-failure-mode restores | `dr_drill.sh` measures this quarterly. |

If a drill produces RTO > 60 minutes, the drill is logged as a "miss"
in `INCIDENT_LOG.md` and the next quarter's plan must include a
mitigation.

---

## Quarterly Drill Schedule

| Quarter | Window | Driver | What we time |
|---------|--------|--------|--------------|
| Q1 | First Saturday of January | Claude | full DR drill on scratch VPS |
| Q2 | First Saturday of April | Claude | DR drill + chaos drill back-to-back |
| Q3 | First Saturday of July | Claude | full DR drill (rotate to a new region) |
| Q4 | First Saturday of October | Founder + Claude | full DR drill + tabletop "what if AWS ap-south-1 vanishes" |

Drill = run `scripts/dr_drill.sh --rehearse` end-to-end with a clean
scratch VPS, time every step, log to `INCIDENT_LOG.md`.

---

## Disaster scenarios + playbooks

### Scenario A — Application server is dead (single node)

* **Symptom:** `/api/v1/health` returns 5xx or doesn't respond.
* **Detection:** Prometheus blackbox alert fires; Sentry uptime drops.
* **Response (max 5 min):**
  1. `ssh app-01.trainplex.in`
  2. `bash backend/scripts/auto_heal_check.sh` — verifies whether
     systemd has auto-restarted gunicorn yet.
  3. If still down: `systemctl restart trainplex-gunicorn`.
  4. Verify `/api/v1/health` returns ok within 30s.
  5. If restart didn't work in 60s: `bash backend/scripts/scale_up.sh`
     to spin up `app-02` and shift traffic.
  6. Log to `INCIDENT_LOG.md`.

### Scenario B — Postgres is unreachable

* **Symptom:** every request returns 500; logs say "connection refused"
  to `db-01.trainplex.in`.
* **Detection:** Prometheus `postgres` job stops scraping; app logs
  spike.
* **Response (max 30 min):**
  1. `ssh db-01.trainplex.in`
  2. `systemctl status postgresql` — if dead, `systemctl restart` it.
     **STOP HERE** if it comes back up and `psql -c "SELECT 1"` works.
  3. If the DB host itself is gone: provision a replacement via
     `scripts/dr_drill.sh --real` (founder approval required).
  4. Restore from latest backup via `restore_db.sh`.
  5. Re-point app servers at the new DB host (`/etc/trainplex/env.sh`).
  6. Verify `/api/v1/health/deep` returns `{"db":"ok",...}`.

### Scenario C — Database corruption (queries return wrong rows)

* **Symptom:** consensus engine returns the same submission for
  multiple reviewers; row counts drop unexpectedly; foreign key errors.
* **Detection:** verifier cron job (`verify_backup.sh`) catches >10%
  count regression; reviewers complain in WA.
* **Response (max 60 min):**
  1. Put the platform in read-only mode (revoke writes on the app's DB user).
  2. Snapshot the corrupted DB to `/backups/corrupted-$(date +%s).dump`
     for forensics (don't drop yet).
  3. Restore the latest *good* backup (the one before the verifier
     started failing) into a new DB.
  4. `bash backend/scripts/verify_migration.py` against the restored DB
     to confirm row counts vs. the corrupted snapshot.
  5. Cut traffic to the new DB. Same nginx flip pattern as the LS → fork
     cutover (see `PRODUCTION_CUTOVER_CHECKLIST.md`).
  6. Founder communicates the data-loss window (which submissions
     vanish) to affected trainers via WA.

### Scenario D — Region-wide outage (cloud provider down)

* **Symptom:** entire VPS pool unreachable.
* **Detection:** external probes fail; status pages show provider
  outage.
* **Response (max 4 hours):**
  1. Founder declares region-down in WA ops channel.
  2. Spin up `app-eu-01` + `db-eu-01` in a different region via
     `scripts/dr_drill.sh --real` (the same playbook works against
     a different region; only `REGION=eu-west-1` differs).
  3. Restore latest off-region backup (we ship to Backblaze B2 which is
     multi-region by default).
  4. Update DNS — temporary failover record to the EU pool.
  5. When the original region comes back: snapshot the EU DB, fail
     traffic back, replay EU writes on top of the original DB.

---

## Backup architecture

```
prod Postgres  ──pg_dump nightly──▶  scratch host  ──upload──▶  Backblaze B2
                                  │                                 │
                                  └─── verify_backup.sh nightly ────┘
                                              │
                                              └── alerts to INCIDENT_LOG.md
```

* **Frequency:** every night at 02:00 IST.
* **Retention:** 7 daily, 4 weekly, 12 monthly on B2; oldest deleted
  via lifecycle policy.
* **Verification:** every night, `verify_backup.sh` restores the latest
  dump to a scratch DB, counts rows, compares to previous night.
* **Encryption:** if `$BACKUP_GPG_KEY` is set, every dump is GPG-encrypted
  before upload. Recommended for prod.

---

## Roles + escalation

| Role | Who | When |
|------|-----|------|
| First responder | Whoever sees the Prometheus alert first (Founder or Claude) | Always |
| DB owner | Founder | Postgres-specific issues |
| App owner | Claude | Django / app server issues |
| Comms | Founder | Trainer-facing WA, public status |
| Decision-maker on data loss | Founder | Always |

Founder rule honoured: **Founder's personal mobile is not in any
outbound communication** — alerts go to the ops channel webhook, not
to a phone number.

---

## RTO/RPO drill template

A passing quarterly drill looks like this in `INCIDENT_LOG.md`:

```
## 2026-07-04 — DR_DRILL_OK
* script: dr_drill.sh
* mode: rehearse
* detail: total=1842s mode=rehearse
* operator: vinod@founder-laptop
```

A failing drill looks like:

```
## 2026-07-04 — DR_DRILL_SLOW
* script: dr_drill.sh
* mode: rehearse
* detail: total=4321s mode=rehearse
* root cause: pg_restore -j parallel level too low; bumped to 4 in next quarter
```

The "root cause" line is appended by the operator after the drill, so
the founder can scan the log and see every miss → mitigation.

---

## 3-line Hindi recap for founder

* **Kya bug tha:** DR ka koi structured plan nahi tha — agar DB fail ho jaye to founder ko bina runbook ke gunge hath chalna padta.
* **Usse kya ho rha tha:** RTO/RPO targets sirf hawa me likhe the; backup verifier kaam nahi karta tha; quarterly drill ka koi schedule nahi tha.
* **Ab fix ke baad kya hoga:** Concrete 60-min RTO + 24h RPO, 4 disaster scenarios ke playbook (app down / DB down / corruption / region outage), nightly `verify_backup.sh` jo backup restorable hai ya nahi check karta hai, quarterly `dr_drill.sh` rehearsal jo full restore time karta hai. Founder ke liye sign-off template + escalation roles clearly written.
