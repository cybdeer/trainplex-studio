# LS → Fork Rollback Procedure

The rollback script — `backend/scripts/rollback_to_ls.sh` (bash) and
`backend/scripts/rollback_to_ls.ps1` (PowerShell) — flips nginx routing
back to the legacy Label Studio container in **under 60 seconds**.
This document is the founder's operating manual for that script.

---

## When to rollback

Rollback only if **one or more** of the following are true *within the
30-day post-cutover window* (the LS container is preserved for exactly
30 days after `T-0`):

| Trigger | Detected by | Decision |
|---------|-------------|----------|
| Verification fails 2 hours in a row | hourly cron → WA webhook | rollback |
| > 5% of trainers report missing tasks within 24h | founder inbox | rollback |
| Annotation results render blank for ≥ 3 random trainers | smoke test | rollback |
| Phase 8 cross-check shows drift after smoke window | `verify_migration.py` | rollback |
| Founder loses confidence ("kuch galat ho raha hai") | gut check | rollback |

Anything outside the 30-day window: **do not rollback** — LS container is
gone. File a hotfix instead.

---

## How long it takes

| Step | Time |
|------|------|
| 1. Flip nginx routing flag | ~5 sec |
| 2. nginx reload | ~5 sec |
| 3. Confirm LS container up | ~10 sec (already running in standby) |
| 4. Webhook notify (optional) | ~5 sec |
| 5. Incident log append | ~1 sec |
| **Total** | **~30-60 seconds** |

If `--drop-fork` is passed, the founder prompt + DB drop adds 30-60
additional seconds.

---

## Data preservation guarantees

| Asset | Preserved? | How long | Notes |
|-------|-----------|----------|-------|
| LS production DB | Yes | 30 days (cold-storage snapshot beyond) | Read-only during cutover; new writes after rollback go back to it |
| LS container image | Yes | 30 days | `docker tag` snapshot + `docker save` to NFS |
| Fork DB rows | Yes (default) | Indefinite — operator deletes | `--drop-fork` removes them |
| Fork submissions made AFTER T-0 | **At risk** if rollback in the first hour | Variable | The migration is idempotent for *backfill* but submissions made on the fork after cutover are NOT auto-replayed to LS; founder must export + re-import |
| Annotations history | Yes | Indefinite | LS DB never deleted; just paused |

---

## Running the script

Bash (Linux / WSL):

```bash
backend/scripts/rollback_to_ls.sh --reason "5% of trainers reporting missing tasks"
# Or with DB drop:
backend/scripts/rollback_to_ls.sh --drop-fork --reason "post-cutover audit failed"
```

PowerShell (Windows ops host):

```powershell
backend\scripts\rollback_to_ls.ps1 -Reason "5% of trainers reporting missing tasks"
# Or with DB drop:
backend\scripts\rollback_to_ls.ps1 -DropFork -Reason "post-cutover audit failed"
```

### Environment knobs

| Variable | Default (Linux) | Default (Windows) | Purpose |
|----------|-----------------|--------------------|---------|
| `TRAINPLEX_ROUTE_FLAG` | `/etc/nginx/conf.d/trainplex_upstream.flag` | `C:\TrainPlex\nginx\trainplex_upstream.flag` | Touch-file that nginx-reload watches |
| `TRAINPLEX_INCIDENT_LOG` | `/var/lib/trainplex-data/INCIDENT_LOG.md` | `C:\TrainPlex\data\INCIDENT_LOG.md` | Append-only audit log |
| `LS_COMPOSE` | `/opt/labelstudio/docker-compose.yml` | `C:\TrainPlex\labelstudio\docker-compose.yml` | Compose file to restart LS if down |
| `TRAINPLEX_OPS_WEBHOOK` | unset → no-op | unset → no-op | Outbound notify endpoint |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Routing flipped + LS container up |
| `2` | Operator typed anything other than `YES` at the drop-fork prompt |
| `3` | nginx config dir missing or not writable |
| `4` | `docker compose up` for LS container failed |

### Founder rules honoured

- The script never emits the founder's personal mobile to any log,
  webhook, or notification — the WA webhook payload is structured JSON
  with only `event/reason/at` fields.
- Every rollback appends a row to `INCIDENT_LOG.md` with timestamp,
  reason, and whether fork DB was dropped. Same audit-trail rule as
  the migration apply path.
- Re-running the script is a no-op once the routing flag is written —
  matches the "one-shot root-cause fix" memory rule.

---

## Founder 3-line Hindi recap

- Kya bug hota tha agar rollback na hota: agar fork pe data corrupt mil
  jata ya 5% trainers ka history gum hota, founder ke paas LS pe wapas
  jaane ka koi safe button nahi tha — production downtime ho jata.
- Usse kya hota tha: trainers stuck, payouts halt, founder ad-hoc SQL
  likhne baith jata raat ko 2 baje, aur LS container shayad already
  delete ho chuka hota kyunki backup policy clear nahi thi.
- Ab fix ke baad kya hoga: 30-day SLA pe LS container preserved + image
  snapshot, ek shell command (`rollback_to_ls.sh`) 60 sec me nginx
  flag flip + LS container confirm + WA notify + incident log append
  kar deti hai. PowerShell wrapper bhi hai Windows host ke liye — agar
  bash mile to delegate kar deti hai single canonical implementation
  rakhne ke liye.
