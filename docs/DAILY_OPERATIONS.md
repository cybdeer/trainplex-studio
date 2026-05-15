# TrainPlex Studio — Daily Operations Routine

**Owner:** Founder (driver), Claude (executor of automated checks).

**Purpose:** the 10-minute daily routine. Doing this every weekday morning
catches 90% of issues before trainers notice.

---

## Morning — 09:00 IST (10 minutes total)

### 1. Read the dashboard (2 min)

Open https://prom-01.trainplex.in:3000 → "TrainPlex — System Health".

Green to look for:
* All panels show data (no "No data")
* p95 latency under 400ms
* Error rate at 0
* All probes green

Red to look at:
* Any single yellow/red panel — note the panel name + paste into the
  morning standup message.

### 2. Read the business dashboard (2 min)

Switch to "TrainPlex — Business Metrics".

* Submissions/hour: yesterday's total vs day-before-yesterday
* Active trainers (24h): expected = roster size ± 10%
* Open quality alerts: 0 ideal, > 5 is a yellow flag
* Payouts released today (₹): matches what the founder expects

### 3. Read INCIDENT_LOG.md (1 min)

```bash
tail -50 /var/lib/trainplex-data/INCIDENT_LOG.md
```

Look for new rows since yesterday's check. Any `*_FAIL` or `*_REGRESSION`
warrants action.

### 4. Read Sentry inbox (2 min)

* New unresolved issues since yesterday → triage with SEV ladder from
  `BUG_TRIAGE_PLAYBOOK.md`.
* SEV-1/SEV-2: act now.
* SEV-3/SEV-4: add to backlog.

### 5. Verify nightly cron jobs ran (1 min)

```bash
ssh ops-01.trainplex.in
ls -la /var/lib/trainplex-data/verify/last_counts.json
# Should be timestamped ≤ 24h ago.
```

If older: nightly verifier didn't run. Check cron + manually trigger:
```bash
bash /opt/trainplex/scripts/verify_backup.sh
```

### 6. Read trainer WA ops channel (2 min)

Scroll new messages since yesterday. Any "X kaam nahi kar raha" goes
to the bug funnel (`BUG_TRIAGE_PLAYBOOK.md` → Reproduce step).

---

## Afternoon — 14:00 IST (5 min, opportunistic)

* Glance at the dashboards again — confirms morning numbers are still
  on track for the day.
* If a feature flag rollout is in progress: check the % rollout is
  matching what you set.
* Check the payout queue: rows in `pending` for > 6 hours → investigate.

---

## End of day — 19:00 IST (5 min)

### Pre-night checklist

* [ ] No SEV-1 or SEV-2 open
* [ ] Tomorrow's expected load (broadcasts, payout day) is anticipated
      — scale up ahead if needed (`SCALING_PLAYBOOK.md`)
* [ ] Backup running (cron will fire at 02:00 IST, but check no obvious
      blockers)
* [ ] On-call rotation confirmed for the night (Founder + Claude both
      available; if Founder is travelling, Claude is sole on-call —
      escalation path is the ops WA channel)

---

## Weekly — Monday 09:30 IST (30 min)

### 1. Read BUILD_LOG.md week section

Catch up on what shipped last week. Note any "TODO" or "Phase 2 swap"
items that should now be done.

### 2. Run last week's `verify_backup.sh` history

```bash
grep VERIFY /var/lib/trainplex-data/INCIDENT_LOG.md | tail -7
```

Expect 7 `VERIFY_OK` rows. Any `VERIFY_REGRESSION` → investigate
immediately (data loss in flight).

### 3. Review Sentry weekly digest

`Settings → Email → Weekly Reports` — Founder reads the Monday digest.

### 4. Plan the week's drill (if any quarter-boundary)

Quarter starts on Jan/Apr/Jul/Oct — first Saturday of that month is
the next chaos drill (`CHAOS_RUNBOOK.md`).

---

## Monthly — first Monday (60 min)

### 1. Drill rehearsal

If it's the first month of a quarter, run the drill. Otherwise, skip.

### 2. Cost review

* Pull cloud bill for the month.
* Compare to `SCALING_PLAYBOOK.md` capacity guardrails.
* If overspend: identify cause (extra app server kept up, large
  storage, etc.) and act.

### 3. Founder-Claude alignment session

* Read `BUILD_LOG.md` Phase 1 / Phase 2 status.
* Founder shares what they wish was easier.
* Claude shares what's flaky / slow.
* Agreed actions land in the backlog with deadlines.

---

## Automation (already cron'd)

| Cron | What | Owner |
|------|------|-------|
| `0 2 * * *` | `backup_db.sh prod` | ops-01 |
| `0 3 * * *` | `verify_backup.sh` | ops-01 |
| `*/5 * * * *` | Prometheus scrape (built-in, not cron) | prom-01 |
| `0 9 * * 1` | Sentry weekly digest email | saas |

Don't add cron jobs without updating this table.

---

## Anti-patterns

* **Don't** skip the morning 10-min routine because "I'm busy". The
  routine is shorter than the average bug it catches.
* **Don't** auto-resolve alerts without reading them. Even a flaky
  alert is data — three flakes in a month means the alert is wrong.
* **Don't** ignore yellow Grafana panels because they're not red yet.
  Yellow is "fix this week"; red is "fix today".

---

## 3-line Hindi recap for founder

* **Kya bug tha:** Roz subah agarwal bhai banke dashboard kholne ka habit nahi tha — pehli kabhi-kabhi 2pm pe pata chalta tha ki overnight koi cron fail ho gaya tha.
* **Usse kya ho rha tha:** Reactive culture — alert aati to fix karte. Proactive checks (backups verified, queue lengths, sentry inbox) ka koi structured timing nahi tha.
* **Ab fix ke baad kya hoga:** `DAILY_OPERATIONS.md` 10-min morning routine + 5-min afternoon + 5-min end-of-day + 30-min weekly + 60-min monthly cadence define karta hai. Har step pe exact tab/dashboard/file open karna hai, exact red flags listed. Founder bina kuch socke top-to-bottom tick kar sakta hai aur 90% issues trainer ko pata chalne se pehle hi catch kar leta hai.
