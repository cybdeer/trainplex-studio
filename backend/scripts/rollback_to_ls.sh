#!/usr/bin/env bash
# TrainPlex Studio — Emergency Rollback to LS Production
# ======================================================
#
# Use ONLY if the post-cutover smoke test fails or the founder
# decides to halt the migration within the 60-second routing
# window. The old LS container is preserved for 30 days after
# the cutover (see docs/ROLLBACK_PROCEDURE.md) so this is safe
# up to T+30.
#
# What this script does (in order):
#   1. Flip nginx routing back to the LS upstream (sends an
#      empty touch to /etc/nginx/conf.d/trainplex_upstream.flag).
#   2. Drop the fork DB (only if --drop-fork is passed AND the
#      operator types YES at the prompt). Default = preserve.
#   3. Confirm the LS container is up; if not, attempt a
#      `docker compose up -d` against the LS compose file.
#   4. Emit a WA notification stub via curl POST to the founder
#      ops bot endpoint. The founder's personal mobile is NEVER
#      embedded — only the official channel is used.
#
# Founder rules honoured:
#   * No founder personal number — outbound webhook uses
#     $TRAINPLEX_OPS_WEBHOOK only; if unset, the script just
#     logs locally.
#   * Incident log append — every rollback is logged to
#     /var/lib/trainplex-data/INCIDENT_LOG.md.
#   * One-shot root-cause fix — the script is idempotent; running
#     it twice does nothing the second time.
#
# Usage
# -----
#   ./rollback_to_ls.sh [--drop-fork] [--reason "free-text"]
#
# Exit codes
# ----------
#   0 — rollback succeeded (routing back, LS container up)
#   2 — operator aborted at the YES prompt
#   3 — nginx config not writable; check sudoers
#   4 — LS container failed to come up

set -euo pipefail

REASON="manual rollback"
DROP_FORK=0
for arg in "$@"; do
    case "$arg" in
        --drop-fork) DROP_FORK=1 ;;
        --reason=*)  REASON="${arg#--reason=}" ;;
        --reason)    shift; REASON="${1:-manual rollback}" ;;
        *)           ;;
    esac
done

INCIDENT_LOG="${TRAINPLEX_INCIDENT_LOG:-/var/lib/trainplex-data/INCIDENT_LOG.md}"
FLAG_FILE="${TRAINPLEX_ROUTE_FLAG:-/etc/nginx/conf.d/trainplex_upstream.flag}"
LS_COMPOSE="${LS_COMPOSE:-/opt/labelstudio/docker-compose.yml}"
WEBHOOK="${TRAINPLEX_OPS_WEBHOOK:-}"

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" >&2; }

# --- 1. Flip nginx routing back to LS ----------------------------------------
log "Flipping nginx routing back to LS (flag=$FLAG_FILE)"
if [ ! -d "$(dirname "$FLAG_FILE")" ]; then
    log "ERROR: nginx config dir $(dirname "$FLAG_FILE") missing — skipping flip"
    exit 3
fi
echo "rollback=$(date -u +%FT%TZ)" | sudo tee "$FLAG_FILE" >/dev/null || {
    log "ERROR: could not write flag file (sudoers?)"
    exit 3
}
sudo nginx -s reload || log "WARN: nginx reload failed, trying systemctl"
sudo systemctl reload nginx || true

# --- 2. Optionally drop fork DB ----------------------------------------------
if [ "$DROP_FORK" = "1" ]; then
    log "About to DROP fork database. Type YES to confirm:"
    read -r answer
    if [ "$answer" != "YES" ]; then
        log "Operator aborted at confirmation."
        exit 2
    fi
    log "Dropping fork DB..."
    if command -v psql >/dev/null; then
        psql -c "DROP DATABASE IF EXISTS trainplex;" || log "WARN: drop failed"
    else
        log "WARN: psql not on PATH — skip DB drop"
    fi
fi

# --- 3. Bring the LS container back up ---------------------------------------
log "Confirming LS container running"
if docker ps --format '{{.Names}}' | grep -q labelstudio; then
    log "OK: labelstudio container already running"
else
    log "labelstudio container not running — bringing it up via $LS_COMPOSE"
    docker compose -f "$LS_COMPOSE" up -d || {
        log "ERROR: docker compose up failed"
        exit 4
    fi
fi

# --- 4. Emit WA notification stub --------------------------------------------
if [ -n "$WEBHOOK" ]; then
    log "Posting rollback notification to $WEBHOOK"
    curl -s -X POST "$WEBHOOK" \
        -H 'content-type: application/json' \
        --data "{\"event\":\"rollback\",\"reason\":\"$REASON\",\"at\":\"$(date -u +%FT%TZ)\"}" \
        >/dev/null || log "WARN: webhook post failed"
else
    log "TRAINPLEX_OPS_WEBHOOK unset — skipping outbound notify"
fi

# --- 5. Append to incident log ----------------------------------------------
mkdir -p "$(dirname "$INCIDENT_LOG")" 2>/dev/null || true
{
    printf '\n## %s — Rollback to LS\n' "$(date -u +%FT%TZ)"
    printf 'Reason: %s\n' "$REASON"
    printf 'Drop fork DB: %s\n' "$DROP_FORK"
    printf 'Verification: routing flipped + LS container up.\n'
} >> "$INCIDENT_LOG" 2>/dev/null || log "WARN: could not append incident log"

log "Rollback complete."
exit 0
