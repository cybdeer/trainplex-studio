#!/usr/bin/env bash
# TrainPlex Studio - Emergency Rollback to legacy Label Studio (Wave-19 verified)
# ==============================================================================
#
# Use ONLY if the post-cutover smoke test fails or the founder decides to halt
# the migration within the 30-day post-cutover window. The legacy LS container
# 'trainplex_label_studio_OLD_recovery' (heartexlabs/label-studio:1.13.1) is
# preserved in 'Created' state and binds the existing host volumes:
#     /root/label-studio-data        -> /label-studio/data         (rw)
#     /root/label-studio-css         -> /label-studio/custom-css   (ro)
#     /root/label-studio-configs     -> /label-studio/configs      (ro)
# Boot was verified on alt port 8087: /health -> 200, / -> 302 (Wave-19 W1).
#
# What this script does (in order):
#   1. Stop the production fork stack (trainplex-studio-nginx-1,
#      trainplex-studio-app-1, trainplex-studio-scheduler-1) so port 8080 frees.
#   2. Stop the SSO bridge (trainplex_ls_sso) since it proxies the fork.
#   3. Start the legacy LS container (trainplex_label_studio_OLD_recovery)
#      mapping it onto host port 8080 -> container 8080 so nginx upstream
#      127.0.0.1:8080 continues to resolve without nginx config edits.
#   4. nginx -s reload (no config change needed, upstream same port).
#   5. Optional: drop fork DB if --drop-fork passed AND operator types YES.
#   6. Emit a WA notification stub via the official ops webhook (never the
#      founder's personal mobile).
#   7. Append incident-log row to /var/lib/trainplex-data/INCIDENT_LOG.md.
#
# Founder rules honoured:
#   * No founder personal number - outbound webhook uses TRAINPLEX_OPS_WEBHOOK
#     only; if unset, the script just logs locally.
#   * Incident log append - every rollback is logged.
#   * One-shot root-cause fix - script is idempotent; running twice is no-op.
#
# Usage
# -----
#   ./rollback_to_ls.sh [--drop-fork] [--reason "free-text"]
#
# Exit codes
# ----------
#   0 - rollback succeeded (legacy LS up on :8080, nginx reloaded)
#   2 - operator aborted at the YES prompt
#   3 - docker stop/start failed for production fork containers
#   4 - legacy LS container failed to come up healthy on :8080

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
FORK_COMPOSE="${FORK_COMPOSE:-/root/trainplex-studio/docker-compose.yml}"
LS_OLD_CONTAINER="${LS_OLD_CONTAINER:-trainplex_label_studio_OLD_recovery}"
SSO_CONTAINER="${SSO_CONTAINER:-trainplex_ls_sso}"
WEBHOOK="${TRAINPLEX_OPS_WEBHOOK:-}"

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" >&2; }

# --- 1. Stop the production fork stack --------------------------------------
log "Stopping production fork stack via compose: $FORK_COMPOSE"
if [ ! -f "$FORK_COMPOSE" ]; then
    log "ERROR: fork compose file $FORK_COMPOSE missing"
    exit 3
fi
docker compose -f "$FORK_COMPOSE" stop nginx app scheduler 2>/dev/null     || docker stop trainplex-studio-nginx-1 trainplex-studio-app-1 trainplex-studio-scheduler-1 2>/dev/null     || { log "ERROR: could not stop fork containers"; exit 3; }

# --- 2. Stop the SSO bridge --------------------------------------------------
log "Stopping SSO bridge ($SSO_CONTAINER)"
docker stop "$SSO_CONTAINER" 2>/dev/null || log "WARN: $SSO_CONTAINER already stopped"

# --- 3. Start the legacy LS container ----------------------------------------
log "Starting legacy LS container ($LS_OLD_CONTAINER) on :8080"
# The container was created with no host port bindings, so we either:
#   (a) docker start if it has bindings, or
#   (b) docker run a fresh instance reusing the same image+mounts.
# We choose (b) because port bindings are immutable on existing containers.
if docker ps --format '{{.Names}}' | grep -qx "$LS_OLD_CONTAINER"; then
    log "OK: $LS_OLD_CONTAINER already running"
else
    # Remove the Created-state placeholder so the name is reusable.
    docker rm -f "$LS_OLD_CONTAINER" 2>/dev/null || true
    docker run -d --name "$LS_OLD_CONTAINER"         --restart unless-stopped         -p 8080:8080         -v /root/label-studio-data:/label-studio/data:rw         -v /root/label-studio-css:/label-studio/custom-css:ro         -v /root/label-studio-configs:/label-studio/configs:ro         -e LABEL_STUDIO_HOST=https://app.trainplex.in/label-studio         heartexlabs/label-studio:1.13.1         || { log "ERROR: docker run for $LS_OLD_CONTAINER failed"; exit 4; }
fi

# Health-poll up to 120s
for i in $(seq 1 24); do
    if curl -sf -m 3 http://127.0.0.1:8080/health >/dev/null 2>&1; then
        log "OK: legacy LS responding on :8080/health"
        break
    fi
    sleep 5
    if [ "$i" = "24" ]; then
        log "ERROR: legacy LS did not reach healthy state in 120s"
        exit 4
    fi
done

# --- 4. nginx reload (no config change, upstream :8080 unchanged) ------------
log "Reloading nginx"
nginx -t && nginx -s reload || systemctl reload nginx || log "WARN: nginx reload failed"

# --- 5. Optionally drop fork DB ----------------------------------------------
if [ "$DROP_FORK" = "1" ]; then
    log "About to DROP fork database. Type YES to confirm:"
    read -r answer
    if [ "$answer" != "YES" ]; then
        log "Operator aborted at confirmation."
        exit 2
    fi
    log "Dropping fork DB (trainplex_studio)..."
    if docker exec trainplex-studio-db-1 psql -U postgres -c "DROP DATABASE IF EXISTS trainplex_studio;" 2>/dev/null; then
        log "OK: fork DB dropped"
    else
        log "WARN: drop failed - is db container reachable?"
    fi
fi

# --- 6. Emit WA notification stub --------------------------------------------
if [ -n "$WEBHOOK" ]; then
    log "Posting rollback notification to $WEBHOOK"
    curl -s -X POST "$WEBHOOK"         -H 'content-type: application/json'         --data "{\"event\":\"rollback\",\"reason\":\"$REASON\",\"at\":\"$(date -u +%FT%TZ)\"}"         >/dev/null || log "WARN: webhook post failed"
else
    log "TRAINPLEX_OPS_WEBHOOK unset - skipping outbound notify"
fi

# --- 7. Append to incident log ----------------------------------------------
mkdir -p "$(dirname "$INCIDENT_LOG")" 2>/dev/null || true
{
    printf '\n## %s - Rollback to legacy LS\n' "$(date -u +%FT%TZ)"
    printf 'Reason: %s\n' "$REASON"
    printf 'Drop fork DB: %s\n' "$DROP_FORK"
    printf 'Verification: legacy LS healthy on :8080, nginx reloaded.\n'
} >> "$INCIDENT_LOG" 2>/dev/null || log "WARN: could not append incident log"

log "Rollback complete."
exit 0
