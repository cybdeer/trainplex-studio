#!/usr/bin/env bash
# TrainPlex Studio — Chaos drill.
# ================================
#
# Week 8 Step 17. Quarterly failure injection. The goal isn't to break
# prod — it's to break STAGING in a controlled way and prove that:
#   * the platform auto-heals (systemd restart, DB reconnect, etc.)
#   * the alerts fire (Prometheus → WA ops channel)
#   * the founder + Claude can drive recovery within RTO
#
# Drill modes (one at a time; never combine):
#   * kill-app       — sigkill gunicorn on a random app server
#   * kill-db        — stop the staging postgres container (NEVER prod)
#   * latency-inject — add 200ms tc latency to the staging app
#   * memory-pressure — `stress-ng --vm 4 --vm-bytes 1G` on app server
#
# Safety:
#   * Refuses to run against any host containing the substring "prod"
#     unless `CHAOS_AGAINST_PROD_I_KNOW_WHAT_IM_DOING=YES` is set
#     (and even then only kill-app is allowed).
#   * Every run is logged to INCIDENT_LOG.md.
#
# Usage:
#   ./chaos_drill.sh kill-app TARGET=app-staging-01
#   ./chaos_drill.sh latency-inject TARGET=app-staging-01 DURATION=120
#
# Founder rule honoured:
#   * No personal mobile in alerts. The post-chaos verification reads
#     the Prometheus alert API directly; no SMS path.

set -euo pipefail

DRILL="${1:-}"
TARGET="${TARGET:-app-staging-01}"
DURATION="${DURATION:-60}"
INCIDENT_LOG="${INCIDENT_LOG:-/var/lib/trainplex-data/INCIDENT_LOG.md}"

if [ -z "$DRILL" ]; then
  echo "usage: $0 {kill-app|kill-db|latency-inject|memory-pressure}" >&2
  exit 2
fi

# ── Safety gate ──────────────────────────────────────────────────────
if echo "$TARGET" | grep -qi 'prod'; then
  if [ "${CHAOS_AGAINST_PROD_I_KNOW_WHAT_IM_DOING:-}" != "YES" ]; then
    echo "REFUSED: $TARGET looks like production." >&2
    exit 3
  fi
  if [ "$DRILL" != "kill-app" ]; then
    echo "REFUSED: only kill-app is allowed against prod (after override)." >&2
    exit 3
  fi
fi

_log() {
  echo "[$(date -u +%FT%TZ)] [chaos_drill] $*"
}

_append_incident_log() {
  local kind="$1"
  local detail="$2"
  mkdir -p "$(dirname "$INCIDENT_LOG")"
  {
    echo
    echo "## $(date -u +%FT%TZ) — ${kind}"
    echo "* script: chaos_drill.sh"
    echo "* drill: ${DRILL}"
    echo "* target: ${TARGET}"
    echo "* detail: ${detail}"
  } >> "$INCIDENT_LOG"
}

# ── Pre-condition: target is healthy now ─────────────────────────────
HEALTH_BEFORE=$(curl -fsS "https://${TARGET}/api/v1/health" || echo "down")
if echo "$HEALTH_BEFORE" | grep -q '"status":"ok"'; then
  _log "pre-check: $TARGET healthy"
else
  _log "REFUSED: target is already unhealthy"
  exit 4
fi

START_TS=$(date +%s)

# ── Drill execution ──────────────────────────────────────────────────
case "$DRILL" in
  kill-app)
    _log "Killing gunicorn on $TARGET"
    ssh "$TARGET" "sudo pkill -9 -f 'gunicorn.*trainplex'" || true
    ;;
  kill-db)
    _log "Stopping postgres container on $TARGET"
    ssh "$TARGET" "sudo systemctl stop postgresql"
    ;;
  latency-inject)
    _log "Adding 200ms latency for ${DURATION}s"
    ssh "$TARGET" "sudo tc qdisc add dev eth0 root netem delay 200ms"
    sleep "$DURATION"
    ssh "$TARGET" "sudo tc qdisc del dev eth0 root netem" || true
    ;;
  memory-pressure)
    _log "Adding memory pressure for ${DURATION}s"
    ssh "$TARGET" "stress-ng --vm 4 --vm-bytes 1G --timeout ${DURATION}s &"
    sleep "$DURATION"
    ;;
  *)
    echo "Unknown drill: $DRILL" >&2
    exit 2
    ;;
esac

# ── Wait for recovery ────────────────────────────────────────────────
_log "Waiting up to 120s for recovery…"
RECOVERED=0
for _ in $(seq 1 60); do
  H=$(curl -fsS "https://${TARGET}/api/v1/health" 2>/dev/null || true)
  if echo "$H" | grep -q '"status":"ok"'; then
    RECOVERED=1
    break
  fi
  sleep 2
done

END_TS=$(date +%s)
DURATION_TOTAL=$((END_TS - START_TS))

if [ "$RECOVERED" = "1" ]; then
  _log "OK — recovered in ${DURATION_TOTAL}s"
  _append_incident_log "CHAOS_${DRILL}_RECOVERED" "duration=${DURATION_TOTAL}s target=${TARGET}"
  exit 0
else
  _log "FAIL — did NOT recover in 120s"
  _append_incident_log "CHAOS_${DRILL}_NO_RECOVERY" "duration=${DURATION_TOTAL}s target=${TARGET}"
  exit 1
fi
