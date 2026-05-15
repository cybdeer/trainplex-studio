# TrainPlex Studio — Scaling Playbook

**Owner:** Claude (executor), Founder (approver for prod scale events).

**Scope:** when to scale, how to scale, and how to verify the scale
worked. Reactive (responding to load) and proactive (ahead of a
broadcast push).

---

## Capacity baseline (Phase 1)

| Resource | Capacity | Headroom at typical load |
|----------|----------|--------------------------|
| 1 app server (4 vCPU / 8 GB) | ~200 req/s, ~100 concurrent submits | 5× current production (17 trainers) |
| 1 Postgres (4 vCPU / 8 GB) | ~3k qps mixed | 10× current scale |
| 1 Redis (1 vCPU / 1 GB) | 50k ops/s | 50× current |
| nginx (shared host) | line-rate | — |

The load test suite (`loadtest/k6/scenarios/full_workflow.js`)
specifically targets 10× current production — if it holds at SLO, we
have 10× headroom on a 1-server config.

---

## When to scale UP

| Trigger | Action | Owner |
|---------|--------|-------|
| Grafana `system_health` shows p95 > 400ms sustained 15min | scale +1 app server | Claude |
| Grafana `system_health` shows DB conns > 80% pool size for 10min | bump app server count OR raise pool (whichever is faster) | Claude |
| Planned event: WA broadcast to >50 trainers | scale +1 ahead by 30 min | Founder |
| Planned event: payout release window | scale +1 ahead by 1 hr | Founder |
| Load test SLO violation that doesn't recover after `simplify` fix | permanent scale | Founder approves |

## When to scale DOWN

| Trigger | Action | Owner |
|---------|--------|-------|
| Grafana `system_health` shows p95 < 100ms for >24h AND >1 app server | scale -1 app server | Claude (cron) |
| Cost reduction directive | confirm with founder | Founder |

Never scale down to 0. The minimum is 1 (set in
`backend/scripts/scale_up.sh` as `MIN_APP_SERVERS=1`).

---

## How to scale

Use the script — **never** click in the cloud provider UI directly,
because the script also wires nginx upstream + logs the event.

### Scale up by 1

```bash
ssh ops-01.trainplex.in
sudo /opt/trainplex/backend/scripts/scale_up.sh
```

The script:
1. Reads `/etc/trainplex/scale.conf` for current desired count.
2. Invokes ansible to provision a new app server.
3. Adds the new server to `/etc/nginx/conf.d/trainplex_upstream.conf`.
4. Reloads nginx.
5. Polls `/api/v1/health` until ok.
6. Appends to `INCIDENT_LOG.md`.

### Scale to absolute count

```bash
sudo /opt/trainplex/backend/scripts/scale_up.sh --to 3
```

### Scale down

```bash
sudo /opt/trainplex/backend/scripts/scale_up.sh --down
```

Drains the *oldest* server first (LIFO is risky because the youngest
might still be warming up).

---

## Verification after every scale event

```bash
# 1. Each upstream returns ok.
for srv in $(cat /etc/trainplex/scale.conf | grep -oE 'app-[0-9]+'); do
  curl -fsS "https://${srv}.trainplex.in/api/v1/health" | jq .status
done

# 2. nginx is balancing.
for i in 1 2 3 4 5; do
  curl -sI https://trainplex.in/api/v1/health | grep X-Upstream
done

# 3. Grafana `system_health` shows the new server in scrape list.
promtool query instant http://prom-01.trainplex.in:9090 'up{job="trainplex_app"}'

# 4. INCIDENT_LOG.md has the new row.
tail -20 /var/lib/trainplex-data/INCIDENT_LOG.md
```

---

## Anti-patterns (what NOT to do)

* **Don't** scale up DB by adding read replicas before fixing slow
  queries. The fix-the-query path is 10× cheaper.
* **Don't** scale Redis vertically until you've checked `redis-cli
  info | grep evicted_keys` — evictions mean you're under-sized, not
  over-loaded.
* **Don't** scale on a single spike — wait 15 minutes of sustained
  high load. Spikes are usually one bad request, not capacity.
* **Don't** scale on staging-only load. Staging has different traffic
  shape; scale decisions are based on prod metrics only.

---

## Cost guardrails

| Phase | Max app servers | Why |
|-------|-----------------|-----|
| Phase 1 (Week 1-8) | 1 | Solo founder, 17 trainers, no budget yet |
| Phase 2 (Week 9-12) | 3 | Initial growth, founder-approved budget |
| Phase 3+ | 10 (`MAX_APP_SERVERS`) | Hard cap; raise via PR only |

If the `MAX_APP_SERVERS` cap is ever hit in prod, that's a bug — the
capacity model is wrong. Don't raise the cap; fix the model.

---

## 3-line Hindi recap for founder

* **Kya bug tha:** Load spike aate hi panic me cloud console khol ke manually node spin karna padta — koi structured "kab scale, kaise scale, kaise verify" nahi tha.
* **Usse kya ho rha tha:** SLO miss hone pe founder ko aakhri minute me kuchh kaam karna padta; cloud UI me click karne se nginx config aur incident log dono manually update karne padte; scale up/down decision data-driven nahi tha.
* **Ab fix ke baad kya hoga:** `SCALING_PLAYBOOK.md` exact triggers (Grafana metric > X for Y minutes) + exact script call (`scale_up.sh`) + post-scale verification + 3-phase cost guardrails define karta hai. Anti-patterns (slow query > read replica, evictions > over-sized) bhi listed taaki founder galat decision se bach jaye.
