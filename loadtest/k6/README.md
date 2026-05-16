# TrainPlex k6 load tests

Week 8 deliverable — Step 9.5 (Load Test). All scripts run against the
`hostnamed` k6 binary; nothing is installed into the Python venv or the
Node modules.

## Prereqs

```bash
# macOS
brew install k6

# Linux
sudo gpg -k && sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt update && sudo apt install k6

# Windows (Chocolatey)
choco install k6
```

## Target environment

The scenarios are pointed at `staging.trainplex.in` by default. Override:

```bash
k6 run -e BASE=https://my.staging.host scenarios/login_burst.js
```

The synthetic user pool (`trainer000@loadtest.trainplex.in` ...
`trainer099@loadtest.trainplex.in` + `admin00..admin04`) is seeded by
the operator before any run — the loadtest **never** uses real trainer
credentials. The default password is `LoadTest2026!`; override via
`-e LOADTEST_PASSWORD=...`.

⚠️ **Never aim these scripts at production.** They will burn rate limits
and write to the `htx_wa_broadcast_log` table. The CI workflow that
calls into this directory only sets `BASE` to the staging host.

## Scenarios

| Scenario | Workload | SLO |
|----------|----------|-----|
| `login_burst.js` | 100 logins/sec for 60s | login p95 < 500ms, error rate < 1% |
| `task_submit.js` | 100 trainers ramping over 5min, each submits 10 tasks | submit p95 < 600ms, error rate < 1% |
| `dashboard.js` | 50 admins poll the dashboard for 3min | dashboard p95 < 400ms |
| `wa_broadcast.js` | 5 admins x 3 broadcasts of 100 recipients each | broadcast p95 < 1500ms |
| `full_workflow.js` | 80 trainers + 15 admins + 4 reviewers + 1 broadcaster for 15min | global /api/v1/* p95 < 500ms, p99 < 1000ms |

## Running

```bash
cd loadtest/k6
k6 run -e BASE=https://staging.trainplex.in scenarios/login_burst.js
k6 run -e BASE=https://staging.trainplex.in scenarios/task_submit.js
k6 run -e BASE=https://staging.trainplex.in scenarios/dashboard.js
k6 run -e BASE=https://staging.trainplex.in scenarios/wa_broadcast.js
k6 run -e BASE=https://staging.trainplex.in scenarios/full_workflow.js
```

## Targets (Step 9.5 — production cutover gate)

* **Trainers concurrent**: 100 (10x current production scale of 17 trainers).
* **p95 latency**: < 500 ms for any `/api/v1/*` endpoint.
* **p99 latency**: < 1000 ms.
* **Error rate**: < 1% (the k6 `http_req_failed` rate must stay green).

`full_workflow.js` is the deciding scenario for the cutover gate; the
others isolate one bottleneck class at a time and exist so we can blame
the right component when `full_workflow` fails.

## Output

k6 emits a summary at end of run. To pipe into Grafana, add
`--out cloud` (k6 Cloud) or `--out influxdb=http://...`. The
`monitoring/grafana/dashboards/system_health.json` dashboard expects the
k6 metrics under the `loadtest` measurement.

## Founder rules honoured

* **No founder personal number** — none of the synthetic recipients use
  the founder's `<configured-guard>` personal mobile; the helper
  generates `+91900000NNNN` only.
* **One-shot root-cause fix** — every SLO breach must yield a fix to the
  underlying service (more workers, denormalised query, etc.), never a
  loosened threshold. The thresholds in `lib/auth.js` are deliberately
  the production SLO, not "what passes today".
