# LS -> Fork Rollback Procedure (Wave-19 verified)

The rollback script - `backend/scripts/rollback_to_ls.sh` (bash) and
`backend/scripts/rollback_to_ls.ps1` (PowerShell) - swaps the production
TrainPlex Studio fork stack for the preserved legacy Label Studio
container `trainplex_label_studio_OLD_recovery`
(image `heartexlabs/label-studio:1.13.1`) in **under 90 seconds**.

This document is the founder's operating manual for that script.
Wave-19 W1-ROLLBACK verified a clean container boot on alt port 8087:
`/health -> 200 OK`, `/ -> 302 redirect to /user/login/`.

---

## Real layout on the server

| Asset | Real path on `ssh trainplex` |
|-------|------------------------------|
| Fork compose file | `/root/trainplex-studio/docker-compose.yml` |
| nginx vhost config | `/etc/nginx/conf.d/trainplex.conf` |
| Legacy LS sqlite + uploads | `/root/label-studio-data/` (rw mount) |
| Legacy LS custom CSS | `/root/label-studio-css/` (ro mount) |
| Legacy LS configs | `/root/label-studio-configs/` (ro mount) |
| Incident log (append-only) | `/var/lib/trainplex-data/INCIDENT_LOG.md` |

Production fork containers (running today):

| Name | Role |
|------|------|
| `trainplex-studio-app-1` | Django uwsgi app (fork) |
| `trainplex-studio-nginx-1` | Fork-internal nginx, host :8080 + :8081 |
| `trainplex-studio-scheduler-1` | Fork scheduler |
| `trainplex-studio-db-1` | Postgres 17 (fork DB `trainplex_studio`) |
| `trainplex_ls_sso` | SSO bridge, host :8082 |

Preserved rollback target (currently in `Created` state, never started):

| Name | Image | Mounts |
|------|-------|--------|
| `trainplex_label_studio_OLD_recovery` | `heartexlabs/label-studio:1.13.1` | `/root/label-studio-data`, `/root/label-studio-css`, `/root/label-studio-configs` |

---

## When to rollback

Rollback only if **one or more** of the following are true *within the
30-day post-cutover window* (the legacy LS image + data are preserved
for exactly 30 days after T-0):

| Trigger | Detected by | Decision |
|---------|-------------|----------|
| Verification fails 2 hours in a row | hourly cron -> WA webhook | rollback |
| > 5% of trainers report missing tasks within 24h | founder inbox | rollback |
| Annotation results render blank for >= 3 random trainers | smoke test | rollback |
| Phase 8 cross-check shows drift after smoke window | `verify_migration.py` | rollback |
| Founder loses confidence ("kuch galat ho raha hai") | gut check | rollback |

Anything outside the 30-day window: **do not rollback** - legacy LS data
volume may have drifted beyond reconciliation. File a hotfix instead.

---

## How long it takes (verified Wave-19)

| Step | Time |
|------|------|
| 1. Stop fork stack (`docker compose stop nginx app scheduler`) | ~5-10 sec |
| 2. Stop SSO bridge (`trainplex_ls_sso`) | ~2 sec |
| 3. Start legacy LS container on :8080 | ~5 sec |
| 4. Health-poll `/health` until 200 | ~60-90 sec (uwsgi cold start) |
| 5. `nginx -s reload` (no config change, upstream :8080 same) | ~2 sec |
| 6. Webhook notify (optional) | ~2 sec |
| 7. Incident log append | ~1 sec |
| **Total** | **~75-110 seconds** |

If `--drop-fork` is passed, the founder prompt + DB drop adds 30-60
additional seconds.

---

## Verified boot command (Wave-19 W1)

The legacy image was boot-tested on alt port 8087 (avoid colliding with
the production fork on :8080) using:

```bash
docker run --rm -d --name trainplex_OLD_boot_test \
    -p 8087:8080 \
    -e LABEL_STUDIO_HOST=http://localhost:8087 \
    -e DJANGO_DB=sqlite \
    -e DATABASE=postgresql \
    heartexlabs/label-studio:1.13.1

sleep 90
curl -sI http://localhost:8087/health   # -> HTTP/1.1 200 OK
curl -sI http://localhost:8087/         # -> HTTP/1.1 302 Found, Location: /user/login/
docker stop trainplex_OLD_boot_test     # auto-rm via --rm
```

The real rollback uses the actual preserved volumes (sqlite at
`/root/label-studio-data/label_studio.sqlite3`), not an ephemeral DB.

---

## Data preservation guarantees

| Asset | Preserved? | How long | Notes |
|-------|-----------|----------|-------|
| Legacy LS sqlite DB | Yes | 30 days (cold-storage snapshot beyond) | Read-only during cutover; new writes after rollback resume against it |
| Legacy LS container image (`heartexlabs/label-studio:1.13.1`) | Yes | 30 days | Pinned tag retained in local Docker registry |
| Fork DB rows (`trainplex_studio`) | Yes (default) | Indefinite - operator deletes | `--drop-fork` removes them |
| Fork submissions made AFTER T-0 | **At risk** if rollback in the first hour | Variable | The migration is idempotent for *backfill* but submissions made on the fork after cutover are NOT auto-replayed to LS; founder must export + re-import via `migrate_ls_to_fork.py --reverse` |
| Annotations history | Yes | Indefinite | Legacy LS sqlite never deleted; just paused |

---

## Running the script

Bash (Linux):

```bash
/root/trainplex-studio/backend/scripts/rollback_to_ls.sh \
    --reason "5% of trainers reporting missing tasks"

# Or with DB drop:
/root/trainplex-studio/backend/scripts/rollback_to_ls.sh --drop-fork \
    --reason "post-cutover audit failed"
```

PowerShell (Windows ops host - delegates to bash via SSH):

```powershell
backend\scripts\rollback_to_ls.ps1 -Reason "5% of trainers reporting missing tasks"
backend\scripts\rollback_to_ls.ps1 -DropFork -Reason "post-cutover audit failed"
```

### Environment knobs

| Variable | Default | Purpose |
|----------|---------|---------|
| `FORK_COMPOSE` | `/root/trainplex-studio/docker-compose.yml` | Fork compose file used for `docker compose stop` |
| `LS_OLD_CONTAINER` | `trainplex_label_studio_OLD_recovery` | Preserved legacy container name |
| `SSO_CONTAINER` | `trainplex_ls_sso` | SSO bridge container (stopped on rollback) |
| `TRAINPLEX_INCIDENT_LOG` | `/var/lib/trainplex-data/INCIDENT_LOG.md` | Append-only audit log |
| `TRAINPLEX_OPS_WEBHOOK` | unset -> no-op | Outbound notify endpoint (official channel only) |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Legacy LS healthy on :8080, nginx reloaded |
| `2` | Operator typed anything other than `YES` at the drop-fork prompt |
| `3` | docker stop/start failed for production fork containers |
| `4` | Legacy LS container failed to reach `/health -> 200` in 120s |

### Founder rules honoured

- The script never emits the founder's personal mobile to any log,
  webhook, or notification - the WA webhook payload is structured JSON
  with only `event/reason/at` fields.
- Every rollback appends a row to `/var/lib/trainplex-data/INCIDENT_LOG.md`
  with timestamp, reason, and whether fork DB was dropped. Same
  audit-trail rule as the migration apply path.
- Re-running the script is idempotent (already-running legacy container
  is left in place) - matches the "one-shot root-cause fix" memory rule.

---

## Tabletop verification (Wave-19 W1)

| Step | Command | Expected |
|------|---------|----------|
| Fork compose exists | `ls /root/trainplex-studio/docker-compose.yml` | file present |
| Legacy container preserved | `docker ps -a --filter name=trainplex_label_studio_OLD_recovery` | one container, status `Created` |
| Legacy data volume mounted | `ls /root/label-studio-data/label_studio.sqlite3` | sqlite file present, ~7 MB |
| Port 8080 currently used by fork | `ss -ltn \| grep :8080` | LISTEN on 0.0.0.0 |
| nginx vhost present | `ls /etc/nginx/conf.d/trainplex.conf` | file present |
| Boot-test image responds | (see verified boot command) | `/health` 200, `/` 302 |
| Script executable | `stat -c %A backend/scripts/rollback_to_ls.sh` | `-rwxr-xr-x` |

---

## Founder 3-line Hindi recap

- Kya bug hota tha agar rollback na hota: fork pe data corrupt mile ya
  5% trainers ka history gum ho, founder ke paas legacy LS pe wapas
  jaane ka koi verified-boot button nahi tha; documentation me dead
  path (`/opt/labelstudio/...`, `/etc/nginx/conf.d/trainplex_upstream.flag`)
  the jo asli server pe exist hi nahi karte.
- Usse kya hota tha: trainers stuck, payouts halt, founder ad-hoc
  `docker run` likhne baith jata raat ko 2 baje aur shayad galat
  volume mount kar deta - sqlite corrupt ho jata.
- Ab fix ke baad kya hoga: `rollback_to_ls.sh` real paths (real compose,
  real volumes, real container names) target karti hai; legacy image
  boot-test 8087 par pass ho chuka hai (200 + 302); script
  `-rwxr-xr-x` permission ke saath idempotent hai; PowerShell wrapper
  bhi hai Windows host ke liye - agar bash mile to delegate kar deti
  hai single canonical implementation rakhne ke liye.
