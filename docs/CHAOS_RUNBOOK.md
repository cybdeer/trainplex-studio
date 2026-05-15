# TrainPlex Studio — Chaos Engineering Runbook

**Owner:** Claude (executor), Founder (decides which drill, when).

**Scope:** quarterly failure injection on the **staging** environment.
The intent is to prove (a) auto-heal works, (b) alerts fire, (c)
on-call humans (Founder + Claude) can drive recovery within RTO.

**Safety:** never run chaos on prod without `CHAOS_AGAINST_PROD_I_KNOW_WHAT_IM_DOING=YES`,
and even then only `kill-app` is allowed (`backend/scripts/chaos_drill.sh`
enforces this).

---

## Schedule

| Quarter | Drill | Driver | Notes |
|---------|-------|--------|-------|
| Q1 | `kill-app` on staging | Claude | Verifies systemd restart |
| Q2 | `latency-inject` 200ms on staging | Claude | Verifies retry + circuit-breaker paths |
| Q3 | `kill-db` on staging | Founder + Claude | Verifies DR runbook Scenario B |
| Q4 | `memory-pressure` on staging | Claude | Verifies OOM-killer + auto-restart |

Drills are scheduled on the first Saturday of the first month of each
quarter, 10:00–12:00 IST window. Founder + Claude are both online for
the duration.

---

## Pre-drill checklist

Before injecting any failure:

- [ ] Grafana `system_health` dashboard open on a second screen
- [ ] Prometheus alert page (`http://prom-01:9090/alerts`) open
- [ ] Sentry inbox open
- [ ] WA ops channel open (alerts are routed here)
- [ ] Last green load test on staging within 7 days
- [ ] `INCIDENT_LOG.md` accessible
- [ ] Rollback path agreed (chaos drills are self-rollback by design,
      but if not, manual restart is the fallback)

---

## Drill: kill-app

**Goal:** verify a dead gunicorn auto-restarts within 30 seconds AND
no traffic is lost (or, if lost, retried by nginx).

**Run:**

```bash
ssh ops-01.trainplex.in
sudo /opt/trainplex/backend/scripts/chaos_drill.sh kill-app TARGET=app-staging-01
```

**Expected timeline:**

| t | Event |
|---|-------|
| 0s | gunicorn SIGKILL'd |
| 1–5s | systemd `Restart=always` kicks in |
| 5–10s | new gunicorn process up; first health probe responds 200 |
| 10–30s | Prometheus blackbox alert fires (it's been > 2 health probe windows red) |
| 30s | WA ops channel pings: "AppDown firing on app-staging-01" |
| 30–60s | gunicorn fully warm; p95 returns to baseline |
| 60–120s | Prometheus alert auto-resolves |

**Pass criteria:**
* gunicorn restarted in < 30s.
* Prometheus alert fired AND auto-resolved.
* No manual intervention needed.
* `INCIDENT_LOG.md` shows `CHAOS_kill-app_RECOVERED`.

**Fail criteria (any one):**
* No auto-restart in 60s.
* No Prometheus alert ever fired (means alerting pipeline is broken;
  far worse than the original outage).
* `INCIDENT_LOG.md` shows `CHAOS_kill-app_NO_RECOVERY`.

---

## Drill: latency-inject

**Goal:** verify the platform degrades gracefully, not catastrophically,
when one app server is slow.

**Run:**

```bash
sudo /opt/trainplex/backend/scripts/chaos_drill.sh latency-inject \
  TARGET=app-staging-01 DURATION=120
```

**What happens:** `tc qdisc` adds 200ms of egress latency to eth0 on
that server for 2 minutes. Other app servers (if any) are unaffected.

**Expected:**
* Grafana shows p95 climb on that one server only.
* If `MIN_APP_SERVERS > 1`: nginx least-conn routes traffic to the
  healthy server; SLO holds.
* If `MIN_APP_SERVERS == 1`: SLO breach on /api/v1/* p95 alerts fire.

**Pass criteria:**
* Latency injection works (you can see it in Grafana).
* Auto-recovery after `DURATION` seconds.
* Alerts fire (single-server case) or are correctly suppressed
  (multi-server case with traffic re-routing).

---

## Drill: kill-db

**Goal:** verify DR runbook Scenario B (DB unreachable) works in
practice, not just on paper.

**Run:**

```bash
sudo /opt/trainplex/backend/scripts/chaos_drill.sh kill-db \
  TARGET=db-staging-01
```

**What happens:** postgres on the staging DB is stopped. Every app
request fails with a DB connection error.

**Expected:**
* `/api/v1/health/deep` returns `{"db":"fail",...}`.
* Prometheus `postgres` job goes red.
* WA ops channel pings: "PostgresDown".
* Founder/Claude restart postgres via the runbook.
* Recovery in < 5 minutes (this is staging, not prod restore).

**Pass criteria:**
* The runbook in `DR_RUNBOOK.md` works step-by-step.
* No surprises (every step works as written).

If any step in the runbook needed improvisation, the runbook is the
artefact to fix — not the drill outcome. Update `DR_RUNBOOK.md` in the
same session.

---

## Drill: memory-pressure

**Goal:** verify the platform doesn't get killed by the OOM killer
on a memory spike. Or, if it does, that it restarts cleanly.

**Run:**

```bash
sudo /opt/trainplex/backend/scripts/chaos_drill.sh memory-pressure \
  TARGET=app-staging-01 DURATION=180
```

**What happens:** `stress-ng --vm 4 --vm-bytes 1G` chews 4 GB of RAM
for 3 minutes.

**Expected:**
* Grafana node_exporter shows memory near full.
* If gunicorn gets OOM'd: systemd auto-restarts (same as kill-app).
* If gunicorn survives: nothing to do; we just have a Grafana panel
  to point at the next time someone says "memory is fine".

---

## Post-drill checklist

After every drill, regardless of outcome:

- [ ] `INCIDENT_LOG.md` entry exists (the script writes it automatically;
      verify the row is there)
- [ ] If pass: BUILD_LOG.md gets a 1-line note in the current week's
      "Drills" subsection
- [ ] If fail: a SEV-3 ticket is opened against whatever component
      didn't auto-heal; assigned to Claude; deadline next sprint
- [ ] Founder + Claude debrief (5 min): "what surprised us? what to
      add to runbooks?"

---

## Anti-patterns

* **Don't** run chaos on prod unless explicitly approved AND it's the
  kill-app drill specifically.
* **Don't** combine drills (e.g. kill-app + kill-db at the same time).
  The point is to isolate which subsystem failed; multi-failure drills
  obscure that.
* **Don't** skip post-drill cleanup. If `tc qdisc` was added by
  latency-inject, the script removes it on exit, but if the script
  crashed mid-drill, manually verify: `ssh app-staging-01 'tc qdisc show dev eth0'`.
* **Don't** silence alerts during a drill. The whole point is to
  verify alerts fire.

---

## 3-line Hindi recap for founder

* **Kya bug tha:** Production system "works on dev box" pe ship hota tha — bina active failure rehearsal ke. Pehli baar agar gunicorn 2am ko mar gaya, founder ko aakhri minute me runbook search karna padta.
* **Usse kya ho rha tha:** Auto-heal claim sirf systemd config me likha hua tha; actual sigkill ke baad recovery time, alert fire time, manual intervention need — kuchh measured nahi tha.
* **Ab fix ke baad kya hoga:** `CHAOS_RUNBOOK.md` 4 quarterly drills define karta hai (`kill-app` / `latency-inject` / `kill-db` / `memory-pressure`). Har drill ka exact script call, expected timeline second-by-second, pass/fail criteria, post-drill checklist. Annual schedule fixed: first Saturday of each quarter. Failures `INCIDENT_LOG.md` me automatically appear, runbook updates same session me hote hain.
