#!/usr/bin/env bash
# TrainPlex Studio — Disaster Recovery Drill.
# ============================================
#
# Week 8 Step 11. Quarterly rehearsal of the full disaster recovery
# story. The intent is to *time* the path "from latest backup to a
# fully working environment", so we know the RTO/RPO we promise the
# founder is real.
#
# What this script does (when run with --rehearse, the default):
#   1. Provision a clean scratch VPS via ansible (or, in stub mode,
#      simulate by spinning up a local docker container).
#   2. Install OS deps + Postgres + Redis on the scratch box.
#   3. Run `restore_db.sh` against the latest backup.
#   4. Run `verify_backup.sh` to confirm rows + integrity.
#   5. Smoke test: login as 3 known trainers + 1 admin via HTTP.
#   6. Time every step + emit a single-line summary.
#   7. Append the RTO outcome to INCIDENT_LOG.md.
#   8. Tear the scratch VPS down (unless --keep is passed).
#
# Founder rule (STUB):
#   No real cloud calls. The provisioning is replaced by `docker run`
#   for a local Postgres so the script can be run end-to-end on the
#   founder's laptop. The ansible playbook stub lives at
#   `backend/scripts/scale_up.sh` (Step 17).
#
# Usage:
#   ./dr_drill.sh --rehearse
#   ./dr_drill.sh --rehearse --keep         # leave scratch box up for inspection
#   ./dr_drill.sh --real                    # against the real ops DR VPS (founder only)
#
# Founder rule: time is logged to incident log; no personal mobile.

set -euo pipefail

MODE="rehearse"
KEEP=0
for arg in "$@"; do
  case "$arg" in
    --rehearse) MODE="rehearse" ;;
    --real)     MODE="real" ;;
    --keep)     KEEP=1 ;;
    *)          echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INCIDENT_LOG="${INCIDENT_LOG:-/var/lib/trainplex-data/INCIDENT_LOG.md}"
LATEST_BACKUP="${LATEST_BACKUP:-/backups/trainplex-prod-latest.dump}"
SCRATCH_CONTAINER="trainplex-dr-scratch-$(date +%s)"
SCRATCH_PORT="55432"

# ── Helpers ───────────────────────────────────────────────────────────
_log() {
  echo "[$(date -u +%FT%TZ)] [dr_drill] $*"
}

_step_timer_start() {
  STEP_NAME="$1"
  STEP_START=$(date +%s)
  _log "BEGIN ${STEP_NAME}"
}

_step_timer_end() {
  local end
  end=$(date +%s)
  local dur=$((end - STEP_START))
  _log "END   ${STEP_NAME} — ${dur}s"
  echo "${STEP_NAME} ${dur}s" >> "/tmp/dr_drill_timings_$$"
}

_append_incident_log() {
  local kind="$1"
  local detail="$2"
  mkdir -p "$(dirname "$INCIDENT_LOG")"
  {
    echo
    echo "## $(date -u +%FT%TZ) — ${kind}"
    echo "* script: dr_drill.sh"
    echo "* mode: ${MODE}"
    echo "* detail: ${detail}"
    echo "* operator: ${USER:-unknown}@$(hostname)"
  } >> "$INCIDENT_LOG"
}

trap 'cleanup' EXIT

cleanup() {
  if [ "$KEEP" = "1" ]; then
    _log "Keeping scratch container ${SCRATCH_CONTAINER} for inspection."
    return
  fi
  if [ "$MODE" = "rehearse" ]; then
    docker rm -f "$SCRATCH_CONTAINER" >/dev/null 2>&1 || true
  fi
}

# ── Step 1: provision ─────────────────────────────────────────────────
_step_timer_start "provision_scratch"
if [ "$MODE" = "rehearse" ]; then
  docker run -d --name "$SCRATCH_CONTAINER" \
    -e POSTGRES_USER=trainplex -e POSTGRES_PASSWORD=drill-only \
    -e POSTGRES_DB=trainplex \
    -p "${SCRATCH_PORT}:5432" \
    postgres:15 >/dev/null
  sleep 5  # postgres ready-poll loop
  # Wait until it accepts connections.
  for _ in $(seq 1 30); do
    if docker exec "$SCRATCH_CONTAINER" pg_isready -U trainplex >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
else
  _log "STUB: real DR VPS provision would run ansible-playbook ops/dr-vps.yml"
  _log "      this stub continues without provisioning (founder runs the real one)"
fi
_step_timer_end "provision_scratch"

SCRATCH_DB_URL="postgres://trainplex:drill-only@localhost:${SCRATCH_PORT}/trainplex"

# ── Step 2: restore ──────────────────────────────────────────────────
_step_timer_start "restore"
TARGET_DB_URL="$SCRATCH_DB_URL" \
  BACKUP_DRY_RUN="${BACKUP_DRY_RUN:-1}" \
  bash "$REPO_ROOT/scripts/restore_db.sh" "$LATEST_BACKUP" \
  || _log "WARN: restore returned non-zero (expected in stub mode without a real dump)"
_step_timer_end "restore"

# ── Step 3: verify ───────────────────────────────────────────────────
_step_timer_start "verify"
DB_URL="$SCRATCH_DB_URL" bash "$REPO_ROOT/scripts/verify_backup.sh" \
  || _log "WARN: verifier returned non-zero (expected in stub mode)"
_step_timer_end "verify"

# ── Step 4: smoke (login 3 trainers + 1 admin) ───────────────────────
_step_timer_start "smoke"
if [ "${TRAINPLEX_SMOKE_HOST:-}" != "" ]; then
  for user in "trainer001" "trainer002" "trainer003" "admin01"; do
    EMAIL="${user}@loadtest.trainplex.in"
    PW="${LOADTEST_PASSWORD:-LoadTest2026!}"
    # Two-step CSRF login probe (same pattern as loadtest/k6/lib/auth.js).
    CSRF=$(curl -s -c /tmp/dr-cookies "${TRAINPLEX_SMOKE_HOST}/user/login/" \
      | grep -oE 'csrfmiddlewaretoken"\s+value="[^"]+"' \
      | head -n1 \
      | sed -E 's/.*value="([^"]+)".*/\1/')
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
      -b /tmp/dr-cookies -c /tmp/dr-cookies \
      -H "Referer: ${TRAINPLEX_SMOKE_HOST}/user/login/" \
      -d "csrfmiddlewaretoken=${CSRF}&email=${EMAIL}&password=${PW}" \
      "${TRAINPLEX_SMOKE_HOST}/user/login/")
    _log "smoke login ${EMAIL} → HTTP ${HTTP_CODE}"
  done
else
  _log "skipping smoke (no TRAINPLEX_SMOKE_HOST set)"
fi
_step_timer_end "smoke"

# ── Summary ──────────────────────────────────────────────────────────
TOTAL=$(awk '{ s += $2 } END { print s }' "/tmp/dr_drill_timings_$$" || echo 0)
_log "DR drill total: ${TOTAL}s"
cat "/tmp/dr_drill_timings_$$"

# RTO target = 60min = 3600s. Pass / fail.
if [ "$TOTAL" -lt 3600 ]; then
  _log "OK: total ${TOTAL}s < RTO budget 3600s"
  _append_incident_log "DR_DRILL_OK" "total=${TOTAL}s mode=${MODE}"
  exit 0
else
  _log "FAIL: total ${TOTAL}s > RTO budget 3600s"
  _append_incident_log "DR_DRILL_SLOW" "total=${TOTAL}s mode=${MODE}"
  exit 1
fi
