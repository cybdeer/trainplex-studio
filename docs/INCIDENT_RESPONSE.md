# TrainPlex Studio — Incident Response

**Owner:** Founder (incident commander), Claude (executor).

**Scope:** the first 15 minutes when production has a problem. Bigger
disasters go to `DR_RUNBOOK.md`. Bug-by-bug triage lives in
`BUG_TRIAGE_PLAYBOOK.md`. This doc is the bridge.

---

## The first 5 minutes — "is it real?"

When an alert fires (Prometheus → WA ops channel, Sentry email,
trainer WA, Grafana red panel):

```
   ┌──────────────────────────────────────┐
   │  1.  ACKNOWLEDGE in WA ops channel    │
   │       "on it" — so the other on-call  │
   │       knows you're driving.           │
   │                                       │
   │  2.  PROBE from outside:               │
   │       curl https://trainplex.in/api/v1/health │
   │       curl https://trainplex.in/user/login/    │
   │                                       │
   │  3.  IS IT REAL? (table below)        │
   └──────────────────────────────────────┘
```

| Symptom | Likely cause | First check |
|---------|--------------|-------------|
| Alert fires + health 5xx | App really down | `ssh app-01 'systemctl status trainplex-gunicorn'` |
| Alert fires + health ok | False positive OR network blip | Wait 2 more minutes; if alert auto-resolves, file as flaky |
| Sentry burst, no alert | Per-user issue | Search Sentry by `user.id` |
| Trainer WA report, no metric | New code path uncovered by tests | Reproduce locally |

---

## The next 10 minutes — "is it auto-healing?"

If it's real and the platform isn't auto-healing within 2 minutes:

```bash
# Step 1: verify the auto-heal layer.
ssh app-01.trainplex.in
sudo /opt/trainplex/backend/scripts/auto_heal_check.sh
```

`auto_heal_check.sh` emits `[OK]/[FAIL]` per check. If everything is
`[OK]` and the platform is still down, the bug is downstream of
auto-heal — proceed to the runbook for the matching disaster scenario.

| auto_heal_check shows | What's wrong | What to do |
|-----------------------|--------------|------------|
| All `[OK]`, platform still down | Bug, not infra | Go to `BUG_TRIAGE_PLAYBOOK.md` |
| `Restart=no` | systemd unit misconfigured | `sudo systemctl edit trainplex-gunicorn` → set `Restart=always` → reload |
| `gunicorn not running` + Restart=always but no auto-restart | Crash loop, exit code != 0 | `journalctl -u trainplex-gunicorn -n 100` |
| `/api/v1/health` slow | Downstream (DB or Redis) slow | Check `/api/v1/health/deep` |

---

## Communication

**During incident:**
* Founder posts a 1-line status to the trainer WA channel within 5 min:
  > "Platform pe issue dikhi hai, fix kar rahe hain. Aap ka data safe hai."
* Status page (`status.trainplex.in`) gets a banner. (Phase 2 work; for
  Phase 1 the founder pings the WA channel manually.)

**After resolution:**
* WA ops channel: "RESOLVED. Root cause: <one line>. Postmortem in 24h."
* `INCIDENT_LOG.md` gets a row.
* If SEV-1 or SEV-2: a 24h postmortem doc lands in `docs/postmortems/`
  (Phase 2 ships the template; for Phase 1, freeform).

**Founder rule:** trainer WA messages never include the founder's personal
mobile. The reply-to is always the official `+91 80 1234 5678` channel
(placeholder; real number set in `core/services/wa_broadcast.py`).

---

## Runbook quick links

| Symptom | Runbook |
|---------|---------|
| App server down | `DR_RUNBOOK.md` Scenario A |
| DB unreachable | `DR_RUNBOOK.md` Scenario B |
| DB corruption | `DR_RUNBOOK.md` Scenario C |
| Region outage | `DR_RUNBOOK.md` Scenario D |
| Functional bug | `BUG_TRIAGE_PLAYBOOK.md` |
| Capacity-related slowness | `SCALING_PLAYBOOK.md` |
| Chaos drill in progress | `CHAOS_RUNBOOK.md` (expected, not an incident) |

---

## Post-incident review template

Within 24 hours of resolution:

```
## YYYY-MM-DD — Postmortem: <one-line title>

### Timeline (UTC)
- HH:MM First alert
- HH:MM Acknowledged by <who>
- HH:MM Root cause identified
- HH:MM Fix applied
- HH:MM Verified resolved

### Severity
SEV-?

### Root cause
One paragraph. Be specific (file path, line number, commit SHA).

### Impact
- Trainers affected: N
- Submissions lost: N (or "none")
- Duration: HH:MM

### What went well
- ...
- ...

### What didn't
- ...
- ...

### Action items (with owner + deadline)
- [ ] @claude: add regression test (deadline: next sprint)
- [ ] @founder: update runbook section X (deadline: this week)
```

The postmortem is **blameless** — focus on systems, not people. The
founder rule `feedback_one_shot_root_fix.md` lives here too: action
items must address the root cause, not just the symptom.

---

## 3-line Hindi recap for founder

* **Kya bug tha:** Alert fire hote hi panic — "kya karoon, kahan dekhoon, kisko bataun" ka kuchh structured nahi tha. Founder + Claude ke beech communication ad-hoc tha.
* **Usse kya ho rha tha:** Real issue ya false positive ka structured diagnosis nahi tha; communication trainer-facing aur ops-facing dono channels me confused tha; postmortem template ki kami se same bug 2x ho jata tha.
* **Ab fix ke baad kya hoga:** `INCIDENT_RESPONSE.md` first 5 min ("is it real") + next 10 min ("is it auto-healing") ke decisions table-driven hai. `auto_heal_check.sh` ka output direct map deta hai action ka. Runbook quick-links ek table me, postmortem template blameless format me. Founder ke trainer-facing 1-line message me personal mobile NEVER (memory rule).
