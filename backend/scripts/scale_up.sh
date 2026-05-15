#!/usr/bin/env bash
# TrainPlex Studio — Scale-Up Playbook (ansible stub).
# ====================================================
#
# Week 8 Step 17. Spin up a new app server when sustained load >
# threshold OR ahead of a planned event (broadcast push, payout day).
#
# STUB notice (founder rule):
#   No real cloud provisioning. The actual `ansible-playbook` call is
#   wrapped in a `BACKUP_DRY_RUN=1`-style guard. The script logs
#   exactly what it would do; founder fills in the cloud API key when
#   ready.
#
# What this script does:
#   1. Read the current desired_app_count from /etc/trainplex/scale.conf.
#   2. Increment by 1 (cap at MAX_APP_SERVERS = 10).
#   3. Render the ansible inventory + extra-vars.
#   4. Invoke `ansible-playbook ops/app-server.yml` (stub).
#   5. Add the new node to /etc/nginx/conf.d/trainplex_upstream.conf.
#   6. Reload nginx; wait for /api/v1/health to return ok.
#   7. Append to INCIDENT_LOG.md.
#
# Inverse operation:
#   `./scale_up.sh --down` decrements and gracefully drains a node.
#
# Usage:
#   ./scale_up.sh                 # +1 app server
#   ./scale_up.sh --down          # -1 app server (oldest)
#   ./scale_up.sh --to 4          # absolute target

set -euo pipefail

SCALE_CONF="${SCALE_CONF:-/etc/trainplex/scale.conf}"
MAX_APP_SERVERS="${MAX_APP_SERVERS:-10}"
MIN_APP_SERVERS="${MIN_APP_SERVERS:-1}"
INCIDENT_LOG="${INCIDENT_LOG:-/var/lib/trainplex-data/INCIDENT_LOG.md}"

DELTA=1
TARGET=""

for arg in "$@"; do
  case "$arg" in
    --down) DELTA=-1 ;;
    --to)   shift; TARGET="$1" ;;
    *)
      if [ -z "$TARGET" ] && [[ "$arg" =~ ^[0-9]+$ ]]; then
        TARGET="$arg"
      fi
      ;;
  esac
done

# Read current count.
[ -f "$SCALE_CONF" ] || echo "desired_app_count=1" | sudo tee "$SCALE_CONF" >/dev/null
CUR=$(grep -oE 'desired_app_count=[0-9]+' "$SCALE_CONF" | cut -d= -f2)

# Compute new.
if [ -n "$TARGET" ]; then
  NEW="$TARGET"
else
  NEW=$((CUR + DELTA))
fi

if [ "$NEW" -lt "$MIN_APP_SERVERS" ]; then
  echo "REFUSED: new count $NEW < MIN $MIN_APP_SERVERS" >&2
  exit 2
fi
if [ "$NEW" -gt "$MAX_APP_SERVERS" ]; then
  echo "REFUSED: new count $NEW > MAX $MAX_APP_SERVERS" >&2
  exit 2
fi

_log() {
  echo "[$(date -u +%FT%TZ)] [scale_up] $*"
}

_append_incident_log() {
  local kind="$1"
  local detail="$2"
  mkdir -p "$(dirname "$INCIDENT_LOG")"
  {
    echo
    echo "## $(date -u +%FT%TZ) — ${kind}"
    echo "* script: scale_up.sh"
    echo "* from: ${CUR}"
    echo "* to: ${NEW}"
    echo "* detail: ${detail}"
  } >> "$INCIDENT_LOG"
}

# ── Stub render of ansible commands ──────────────────────────────────
_log "Scale plan: ${CUR} → ${NEW} app servers"
if [ "$NEW" -gt "$CUR" ]; then
  DIRECTION="up"
  for i in $(seq $((CUR + 1)) "$NEW"); do
    HOST="app-$(printf '%02d' "$i").trainplex.in"
    _log "STUB: would run ansible-playbook ops/app-server.yml \\"
    _log "             --inventory ${HOST}, \\"
    _log "             --extra-vars 'role=app server_id=${i}'"
    _log "STUB: would add ${HOST} to /etc/nginx/conf.d/trainplex_upstream.conf"
  done
elif [ "$NEW" -lt "$CUR" ]; then
  DIRECTION="down"
  for i in $(seq "$CUR" -1 $((NEW + 1))); do
    HOST="app-$(printf '%02d' "$i").trainplex.in"
    _log "STUB: would gracefully drain ${HOST} from nginx upstream"
    _log "STUB: would stop gunicorn + systemctl disable on ${HOST}"
    _log "STUB: would terminate VPS ${HOST} via cloud API"
  done
else
  _log "no-op: target equals current"
  exit 0
fi

# ── Persist new count (only in stub mode; real run waits for ansible OK) ─
echo "desired_app_count=${NEW}" | sudo tee "$SCALE_CONF" >/dev/null

# ── Verify ───────────────────────────────────────────────────────────
_log "STUB: would now poll /api/v1/health on every upstream until all 'ok'"
sleep 1
_log "STUB: health verification passed"

_append_incident_log "SCALE_${DIRECTION^^}_OK" "stub-run; founder to wire real cloud API"

_log "Scale complete. Updated ${SCALE_CONF} to ${NEW}."
_log "Next: monitor Grafana 'TrainPlex — System Health' for 15min."
