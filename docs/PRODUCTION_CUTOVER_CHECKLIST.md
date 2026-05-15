# TrainPlex Studio — Production Cutover Checklist

**Owner of this doc:** Founder (Vinod). Every box must be ticked top-to-bottom
before the routing flip in Step 8.4. This file *extends* `MIGRATION_PLAYBOOK.md`
(which already covers the LS → fork data move). Where this doc references
`MIGRATION_PLAYBOOK.md`, do that first.

**Verification command convention:** every row has a one-liner the operator
copy-pastes. If the command's exit code is non-zero, the box is not ticked.

**Rollback:** at every gate, the rollback is `backend/scripts/rollback_to_ls.sh`
(documented in `ROLLBACK_PROCEDURE.md`). Safe up to T+30 days; after that the
old LS container is decommissioned.

---

## T−7 days — Rehearsal kickoff

| # | Action | Owner | Verification | Sign-off |
|---|--------|-------|--------------|----------|
| 1 | Pull `MIGRATION_PLAYBOOK.md` T-7 steps to completion | Founder | `docs/MIGRATION_REPORT.md` shows zero phase failures | ☐ |
| 2 | Load test against staging — `full_workflow.js` | Claude | `k6 run loadtest/k6/scenarios/full_workflow.js` → all thresholds green | ☐ |
| 3 | Playwright smoke pass on staging | Claude | `cd e2e && pnpm test` → 0 failures on all 3 browsers | ☐ |
| 4 | DR drill rehearsal (verify backup restore on scratch VPS) | Claude | `scripts/dr_drill.sh --rehearse` → RTO < 60min, RPO < 24h | ☐ |
| 5 | Chaos drill: kill app server during submit storm | Claude | `backend/scripts/chaos_drill.sh kill-app` → auto-restart within 30s | ☐ |
| 6 | Sentry alert routes verified | Founder | trigger a synthetic 500 → page received in WA channel | ☐ |
| 7 | Backup verifier scheduled (nightly) | Founder | `crontab -l` lists `verify_backup.sh` | ☐ |
| 8 | Founder reads MIGRATION_AUDIT_REPORT.md template + signs the orphan resolutions | Founder | Each row in `MIGRATION_ORPHANS.md` has decision `create` or `skip` | ☐ |

---

## T−3 days — Sandbox reality check

| # | Action | Owner | Verification | Sign-off |
|---|--------|-------|--------------|----------|
| 1 | Full migration on the staging fork DB (real `--apply`) | Founder | `MIGRATION_REPORT.md` row counts match within tolerance | ☐ |
| 2 | Run verifier on staging | Claude | `python backend/scripts/verify_migration.py …` → zero failures | ☐ |
| 3 | Smoke 5 random trainers' last 30-day history | Founder | every URL returns 200 + visible annotations | ☐ |
| 4 | DNS TTL lowered to 60s (so cutover flip is fast) | Founder | `dig trainplex.in +short` shows TTL ≤ 60 | ☐ |
| 5 | Notify trainers — WA broadcast announcing T-0 window | Founder | `htx_wa_broadcast_log` shows the announcement row | ☐ |
| 6 | Feature flags audit — disable any experimental flag | Founder | `python manage.py shell -c "from core.services.feature_flags import audit; audit()"` → empty list | ☐ |
| 7 | Health endpoint reports green on staging | Claude | `curl https://staging.trainplex.in/api/v1/health` → `{"status":"ok",...}` | ☐ |

---

## T−1 day — Production approval gate

| # | Action | Owner | Verification | Sign-off |
|---|--------|-------|--------------|----------|
| 1 | Fresh full-stack backup of LS prod | Founder | `scripts/backup_db.sh prod` → confirmation row in `INCIDENT_LOG.md` | ☐ |
| 2 | Backup verified by auto-restore-and-rowcount | Claude | `scripts/verify_backup.sh /backups/ls-T1.dump` → exit 0 | ☐ |
| 3 | Sign off by founder — explicit "go" | Founder | reply `GO` in the WA ops channel | ☐ |
| 4 | Maintenance banner published on LS prod | Founder | `https://trainplex.in/` shows banner from `00:00 IST` | ☐ |
| 5 | All cron / scheduler jobs paused | Founder | `crontab -l` is empty for the app user | ☐ |
| 6 | On-call rotation confirmed for T+24h | Founder | Founder + Claude both available; phones on | ☐ |

---

## T−0 — Cutover hour (target window: 02:00–04:00 IST)

| Order | Action | Owner | Verification | Time budget |
|-------|--------|-------|--------------|-------------|
| 1 | Take LS into read-only (drop write privileges on the LS DB user) | Founder | `psql -c "select pg_is_in_recovery()"` returns t / explicit revoke OK | 2 min |
| 2 | Final delta snapshot (any rows since T-1 backup) | Founder | `pg_dump --since=T1 …` produces a delta dump | 5 min |
| 3 | Run `migrate_ls_to_fork.py --apply --i-have-a-backup` against prod fork DB | Claude | exit 0 + `MIGRATION_REPORT.md` row counts ok | 15 min |
| 4 | Run verifier | Claude | `verify_migration.py …` exit 0 | 5 min |
| 5 | Smoke test by Claude (5 random trainers via API) | Claude | each `GET /api/v1/trainer/batch` returns the migrated batch | 3 min |
| 6 | **Flip nginx upstream from `ls_backend` to `trainplex_backend`** | Founder | `curl -sI https://trainplex.in/` → response header `X-Upstream: trainplex` | 1 min |
| 7 | Watch error rate for 10 minutes | Claude | Sentry shows < 5 errors/min, Grafana `system_health` dashboard all green | 10 min |
| 8 | Post-cutover WA broadcast (login link + Hindi note) | Founder | `htx_wa_broadcast_log` shows the new row | 2 min |

### DNS / nginx flip — exact commands

```bash
# On the prod nginx host (as root):
sed -i 's|upstream ls_backend|# upstream ls_backend|' /etc/nginx/conf.d/trainplex.conf
sed -i 's|# upstream trainplex_backend|upstream trainplex_backend|' /etc/nginx/conf.d/trainplex.conf
nginx -t && systemctl reload nginx

# Verify:
curl -sI https://trainplex.in/ | grep -i x-upstream

# If anything looks wrong, IMMEDIATE rollback:
bash backend/scripts/rollback_to_ls.sh
```

The `X-Upstream` header is added by the upstream block; absence means
the request still hit LS, presence means TrainPlex. The rollback script
takes ≈ 60 seconds — see `docs/ROLLBACK_PROCEDURE.md`.

### Cutover abort criteria (rollback NOW)

Rollback immediately and *without further consultation* if any of these
hold within the 10-minute observation window:

* Sentry error rate > 5/min sustained for 2 minutes.
* `/api/v1/health` returns `degraded` or `down` from external probe.
* Any trainer reports they can't see their batch (WA ops channel).
* DB CPU > 80% sustained for 2 minutes.
* p99 latency on `/api/v1/trainer/batch/submit` > 2000ms.

The rollback is **safer** than the cutover — it preserves all migrated
data on the fork DB (read-only after rollback) and re-routes traffic
back to the still-running LS container.

---

## T+1 hour — Hour-1 audit

| # | Action | Owner | Verification |
|---|--------|-------|--------------|
| 1 | Founder logs in as 5 trainers + 1 admin + 1 reviewer | Founder | each landing page renders + key data visible |
| 2 | Run E2E smoke on prod (read-only specs only) | Claude | `pnpm playwright test -g 'logs in'` → green |
| 3 | First payout queue tick | Founder | `htx_payout_queue` rows in `released` for last-hour cohort |

---

## T+24 hours — Day-1 review

| # | Action | Owner | Verification |
|---|--------|-------|--------------|
| 1 | Pull 24h Sentry digest | Founder | error count + top-3 issues filed |
| 2 | Pull 24h Grafana dashboard screenshot | Claude | `monitoring/grafana/dashboards/system_health.json` snapshot |
| 3 | Check incident log appended for every fix | Founder | `INCIDENT_LOG.md` rows since cutover all closed |
| 4 | DNS TTL restored to normal (3600s) | Founder | `dig trainplex.in +short` shows TTL ≈ 3600 |
| 5 | Trainer satisfaction quick poll (WA) | Founder | reply rate > 50% |
| 6 | Founder + Claude post-mortem (what could be smoother next time?) | Both | bullets added to `BUILD_LOG.md` |

---

## T+7 days — Week-1 review

| # | Action | Owner | Verification |
|---|--------|-------|--------------|
| 1 | First weekly DR rehearsal | Claude | `scripts/dr_drill.sh --rehearse` |
| 2 | Backup rotation working (7d retention) | Founder | `ls /backups/` shows 7 daily dumps |
| 3 | First weekly load test on prod-like staging | Claude | `loadtest/k6/scenarios/full_workflow.js` thresholds green |
| 4 | Payout audit — every released payout has a matching WA notify | Founder | join `htx_payout_queue` × `htx_wa_broadcast_log` zero gaps |
| 5 | Founder reads `BUILD_LOG.md` Week-8 section + signs off | Founder | section ends with founder ack |

---

## T+30 days — Decommission gate

| # | Action | Owner | Verification |
|---|--------|-------|--------------|
| 1 | Confirm zero rollback needed in 30 days | Founder | `INCIDENT_LOG.md` has no rollback rows since cutover |
| 2 | LS DB dump archived to long-term storage | Founder | `aws s3 ls s3://trainplex-archive/ls-cutover-T0.dump` |
| 3 | Stop the LS container | Founder | `docker stop ls-prod && docker rm ls-prod` |
| 4 | Drop LS upstream from nginx config | Founder | `grep ls_backend /etc/nginx/conf.d/trainplex.conf` → no match |
| 5 | Final founder sign-off | Founder | reply `LS DECOMMISSIONED` in WA ops channel + log to `BUILD_LOG.md` |

After T+30 the rollback path is no longer available. The fork DB is
the only source of truth.

---

## Sign-off gates (summary)

| Gate | When | Approver | Action if failed |
|------|------|----------|------------------|
| Rehearsal | T-7 | Founder | postpone cutover by 7d |
| Sandbox | T-3 | Founder | identify regression, redo from T-7 |
| Production approval | T-1 | Founder | hard stop until founder explicit "go" |
| Cutover go-no-go | T-0 hour-0 | Founder | abort + reschedule |
| Hour-1 audit | T+1h | Founder | abort + rollback if criteria met |
| Day-1 review | T+24h | Founder | log incidents, no auto-rollback |
| Week-1 review | T+7d | Founder | log + plan fixes |
| Decommission | T+30d | Founder | drop LS, mark cutover closed |

---

## 3-line Hindi recap for founder

* **Kya bug tha:** Bina ek single source-of-truth checklist ke, cutover din founder ko 20 jagah kuchh bhool jane ka risk tha — DNS flip, backup verify, alert routes, WA notify — har ek manually yaad rakhna padta.
* **Usse kya ho rha tha:** Plan me cutover steps `MIGRATION_PLAYBOOK.md` me the lekin operational gates (load test pass, E2E pass, DR drill done, chaos drill done) alag-alag jagah scattered the. Mid-cutover agar ek bhi miss hua to rollback ka koi auto-trigger nahi tha.
* **Ab fix ke baad kya hoga:** `PRODUCTION_CUTOVER_CHECKLIST.md` ek hi page pe T-7 → T+30 ka full plan deta hai — har row pe owner (Founder/Claude), verification command (copy-paste), sign-off gate. Cutover day ke `T-0` slot me 8 ordered steps, 38-min time budget, exact nginx flip command, aur 5 explicit abort criteria — koi ek bhi cross ho to immediately `rollback_to_ls.sh`. Doc khud lock kiya hua flow hai; founder bina socke top-to-bottom tick kar sakta hai.
