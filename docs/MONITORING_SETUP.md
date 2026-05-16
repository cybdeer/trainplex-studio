# TrainPlex Studio — Monitoring Setup

**Scope:** how to wire Sentry + Prometheus + Grafana to production.
Once Step 11 (Week 8) is shipped, this doc is the operator's bible for
spinning a new monitoring stack on a fresh ops VPS.

---

## What gets monitored

| Layer | Tool | What | Alert channel |
|-------|------|------|---------------|
| Application errors | Sentry | Python tracebacks, unhandled exceptions | WA ops channel + email |
| Application performance | Sentry Performance + Prometheus `django-prometheus` | request duration, throughput | Grafana |
| Browser RUM | Sentry Browser SDK + custom `/metrics-rum` endpoint | JS errors, page load time | Grafana |
| Host metrics | Prometheus node_exporter | CPU, RAM, disk, network | Grafana |
| Postgres | postgres_exporter | active conns, slow queries, lock waits | Grafana |
| Redis | redis_exporter | memory, key count, evictions | Grafana |
| Synthetic uptime | blackbox_exporter | `/api/v1/health`, `/user/login/` from outside | Grafana + WA |

---

## Prerequisites

Three VPSes (separate from app VPS for isolation):
* `prom-01.trainplex.in` — Prometheus + Grafana + Alertmanager
* `db-01.trainplex.in` — Postgres + postgres_exporter (same box; cheap)
* `redis-01.trainplex.in` — Redis + redis_exporter (same box)

DNS records pointing the names above.

A Sentry account (saas.sentry.io OR self-hosted; this guide assumes
saas). Two projects:
* `trainplex-backend` — Django Python SDK
* `trainplex-frontend` — JS browser SDK

---

## Step 1: Sentry (errors)

### Backend

Add to `label_studio/core/settings/base.py`:

```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

SENTRY_DSN = os.environ.get("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.05,
        send_default_pii=False,           # founder rule: no PII
        before_send=scrub_founder_mobile, # founder rule: scrub <configured-guard>
        environment=os.environ.get("TRAINPLEX_ENV", "dev"),
        release=os.environ.get("TRAINPLEX_VERSION", "unknown"),
    )
```

`scrub_founder_mobile` lives in `core/utils/sentry_scrubbers.py` (not in
this commit; Phase 2 ships it). The fallback regex is the same one
`backend/scripts/migrate_ls_to_fork.py` uses.

### Frontend

Add to the SPA's `src/main.tsx`:

```ts
import * as Sentry from "@sentry/react";

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    tracesSampleRate: 0.05,
    integrations: [new Sentry.BrowserTracing()],
    beforeSend: (event) => scrubFounderMobile(event),
  });
}
```

### Environment

| Var | Where | Example |
|-----|-------|---------|
| `SENTRY_DSN` | app `.env` | `https://abc@o123.ingest.sentry.io/456` |
| `VITE_SENTRY_DSN` | SPA `.env` | `https://def@o123.ingest.sentry.io/789` |
| `TRAINPLEX_ENV` | both | `prod` / `staging` / `dev` |

---

## Step 2: Prometheus

### Install on `prom-01.trainplex.in`

```bash
# Pin a stable version (Phase 1: 2.55.x).
PROM_VER=2.55.1
wget https://github.com/prometheus/prometheus/releases/download/v${PROM_VER}/prometheus-${PROM_VER}.linux-amd64.tar.gz
tar -xzf prometheus-*.tar.gz
sudo mv prometheus-*/prometheus /usr/local/bin/
sudo mv prometheus-*/promtool /usr/local/bin/
```

### Config

Copy `monitoring/prometheus.yml` from this repo to
`/etc/prometheus/prometheus.yml` on the ops VPS:

```bash
scp monitoring/prometheus.yml prom-01.trainplex.in:/etc/prometheus/prometheus.yml
ssh prom-01.trainplex.in 'sudo systemctl reload prometheus'
```

### Run as systemd

```ini
# /etc/systemd/system/prometheus.service
[Unit]
Description=Prometheus
After=network.target

[Service]
User=prometheus
ExecStart=/usr/local/bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/var/lib/prometheus \
  --storage.tsdb.retention.time=30d \
  --web.listen-address=:9090

[Install]
WantedBy=multi-user.target
```

---

## Step 3: Exporters

### node_exporter (every VPS)

```bash
NX_VER=1.8.2
wget https://github.com/prometheus/node_exporter/releases/download/v${NX_VER}/node_exporter-${NX_VER}.linux-amd64.tar.gz
tar -xzf node_exporter-*.tar.gz
sudo mv node_exporter-*/node_exporter /usr/local/bin/
# systemd unit listening on :9100 (same as scrape config)
```

### postgres_exporter (on `db-01.trainplex.in`)

```bash
PG_EXP_VER=0.16.0
wget https://github.com/prometheus-community/postgres_exporter/releases/download/v${PG_EXP_VER}/postgres_exporter-${PG_EXP_VER}.linux-amd64.tar.gz
# Set DATA_SOURCE_NAME in the systemd unit; user has SELECT on pg_stat_*.
```

### redis_exporter (on `redis-01.trainplex.in`)

```bash
RE_VER=1.61.0
wget https://github.com/oliver006/redis_exporter/releases/download/v${RE_VER}/redis_exporter-v${RE_VER}.linux-amd64.tar.gz
```

### blackbox_exporter (on `prom-01.trainplex.in`)

Probes `/api/v1/health` from outside, so even a fully-broken nginx is
caught.

---

## Step 4: Grafana

```bash
sudo apt install -y grafana
sudo systemctl enable --now grafana-server
```

Default UI on `:3000` — bind to localhost and front with nginx.

### Datasource

`Configuration → Data sources → Add → Prometheus`, URL =
`http://localhost:9090`.

### Dashboards

Import the three dashboards from this repo:

```bash
for d in system_health business_metrics trainer_experience; do
  curl -X POST -H "Content-Type: application/json" \
    -u admin:$GRAFANA_PASSWORD \
    -d @monitoring/grafana/dashboards/${d}.json \
    http://prom-01.trainplex.in:3000/api/dashboards/db
done
```

---

## Step 5: Alertmanager

`/etc/alertmanager/alertmanager.yml` (excerpt):

```yaml
route:
  receiver: 'wa-ops'
  group_by: ['alertname', 'severity']
receivers:
  - name: 'wa-ops'
    webhook_configs:
      - url: 'https://aisensy.com/webhook/...'  # placeholder; founder fills
```

Founder rule reminder: this URL must point to a channel webhook,
NOT to the founder's personal mobile. The AiSensy WA template
sends to the ops group only.

---

## Step 6: Alert rules

Place `/etc/prometheus/rules/trainplex.yml`:

```yaml
groups:
  - name: trainplex
    rules:
      - alert: AppDown
        expr: probe_success{job="blackbox_http",instance=~".*health.*"} == 0
        for: 2m
        labels: { severity: critical }
        annotations:
          summary: "Application health probe failing"
      - alert: HighErrorRate
        expr: sum(rate(django_http_responses_total_by_status_view_method_total{status=~"5..",job="trainplex_app"}[5m])) > 0.5
        for: 5m
        labels: { severity: warning }
        annotations:
          summary: "5xx error rate > 0.5/s for 5m"
      - alert: SlowLogin
        expr: histogram_quantile(0.95, sum by (le)(rate(django_http_requests_latency_seconds_by_view_method_bucket{view=~".*login.*"}[5m]))) > 0.5
        for: 5m
        labels: { severity: warning }
        annotations:
          summary: "Login p95 > 500ms for 5m (SLO breach)"
```

`promtool check rules /etc/prometheus/rules/trainplex.yml` validates
before `systemctl reload prometheus`.

---

## Step 7: Verify end-to-end

```bash
# From any external host:
curl https://trainplex.in/api/v1/health
# Expect: {"status":"ok","db":"ok","redis":"ok","version":"...","uptime_sec":N}

# From the ops VPS:
promtool query instant http://localhost:9090 \
  'up{job="trainplex_app"}'
# Expect: scalar 1

# Trigger a fake error to see Sentry path works:
curl https://trainplex.in/trigger500/
# Should appear in Sentry within 30s.
```

---

## Operational checklist (weekly)

- [ ] Grafana dashboards render without "no data" panels
- [ ] At least one alert fired and resolved in the past 7 days
  (proves the pipeline is alive)
- [ ] `INCIDENT_LOG.md` has an entry for every alert resolved
- [ ] Sentry issue inbox has no critical issues older than 7 days
- [ ] Backup verifier `verify_backup.sh` exit code 0 in last 7 nights

---

## 3-line Hindi recap for founder

* **Kya bug tha:** Production cutover ke baad agar kuchh slow ho ya error aaye to founder ko bina monitoring ke andheri me chalna padta — pata hi nahi chalega ki kya broken hai, kab broken hua, aur kis trainer pe asar hua.
* **Usse kya ho rha tha:** Sentry/Prometheus/Grafana ka koi structured setup doc nahi tha; alerts kab kahan jaate hain ye spec nahi tha; alert routes founder ke personal mobile pe gaye to memory rule break ho jata.
* **Ab fix ke baad kya hoga:** `MONITORING_SETUP.md` step-by-step bole — Sentry kaise wire karo (PII off, founder mobile scrubbed), Prometheus + 4 exporters kaise install karo, 3 Grafana dashboards (system / business / trainer UX) kaise import karo, Alertmanager routes WA ops channel pe — not founder ka phone, alert rules `promtool` se validated. Weekly checklist se founder + Claude verify karte hain pipeline alive hai.
