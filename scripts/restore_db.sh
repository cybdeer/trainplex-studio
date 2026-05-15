#!/usr/bin/env bash
# TrainPlex Studio — DB Restore from a pg_dump custom-format file.
# ================================================================
#
# Week 8 Step 11. Reverse of `backup_db.sh`.
#
# What this script does:
#   1. Download the requested dump from B2 (or use a local path).
#   2. Optionally decrypt with GPG.
#   3. `pg_restore` into $TARGET_DB_URL.
#   4. Append to INCIDENT_LOG.md.
#
# IMPORTANT (founder rule — STUB):
#   No real B2 calls in this commit. Same `BACKUP_DRY_RUN=1` flag
#   behaviour as backup_db.sh — the `_download_from_b2` function logs
#   the would-be command. A local path always works (no stub needed).
#
# Usage:
#   ./restore_db.sh /path/to/trainplex-prod-20260515T120000Z.dump
#   ./restore_db.sh b2://trainplex-backups/trainplex-prod-20260515T120000Z.dump
#
# This script REFUSES to run unless $TARGET_DB_URL is a non-prod DB
# OR $RESTORE_INTO_PROD_I_KNOW_WHAT_IM_DOING=YES is set.

set -euo pipefail

SRC="${1:-}"
INCIDENT_LOG="${INCIDENT_LOG:-/var/lib/trainplex-data/INCIDENT_LOG.md}"
WORKDIR="${RESTORE_WORKDIR:-/tmp/trainplex-restore}"

mkdir -p "$WORKDIR"

_safe_db_url() {
  echo "$1" | sed -E 's#(://[^:]+):[^@]+@#\1:***@#'
}

_log() {
  echo "[$(date -u +%FT%TZ)] [restore_db] $*"
}

_append_incident_log() {
  local kind="$1"
  local detail="$2"
  mkdir -p "$(dirname "$INCIDENT_LOG")"
  {
    echo
    echo "## $(date -u +%FT%TZ) — ${kind}"
    echo "* script: restore_db.sh"
    echo "* source: ${SRC}"
    echo "* target: $(_safe_db_url "${TARGET_DB_URL:-?}")"
    echo "* detail: ${detail}"
    echo "* operator: ${USER:-unknown}@$(hostname)"
  } >> "$INCIDENT_LOG"
}

_download_from_b2() {
  local path="$1"
  local local_path="$2"
  if [ "${BACKUP_DRY_RUN:-0}" = "1" ] || [ -z "${B2_APPLICATION_KEY_ID:-}" ]; then
    _log "STUB download — would have run: b2 download-file-by-name \"${B2_BUCKET:-<unset>}\" \"$path\" \"$local_path\""
    # In stub mode, write a 1-byte placeholder so downstream cmds fail
    # loudly rather than silently restore an empty DB.
    echo "STUB DUMP" > "$local_path"
    return 0
  fi
  b2 authorize-account "$B2_APPLICATION_KEY_ID" "$B2_APPLICATION_KEY"
  b2 download-file-by-name "$B2_BUCKET" "$path" "$local_path"
}

# ── Safety gate ───────────────────────────────────────────────────────
if [ -z "$SRC" ]; then
  _log "ERROR: provide a source (local path or b2:// URL) as arg 1."
  exit 2
fi
if [ -z "${TARGET_DB_URL:-}" ]; then
  _log "ERROR: \$TARGET_DB_URL not set."
  exit 2
fi

if echo "$TARGET_DB_URL" | grep -q 'trainplex-prod'; then
  if [ "${RESTORE_INTO_PROD_I_KNOW_WHAT_IM_DOING:-}" != "YES" ]; then
    _log "REFUSED: target DB looks like production. Set"
    _log "  RESTORE_INTO_PROD_I_KNOW_WHAT_IM_DOING=YES"
    _log "to override (only run after a fresh backup)."
    _append_incident_log "RESTORE_REFUSED" "prod target without override"
    exit 3
  fi
fi

# ── Acquire dump file ─────────────────────────────────────────────────
if [[ "$SRC" == b2://* ]]; then
  REMOTE_PATH="${SRC#b2://}"
  LOCAL_DUMP="${WORKDIR}/$(basename "$REMOTE_PATH")"
  _download_from_b2 "$REMOTE_PATH" "$LOCAL_DUMP"
else
  LOCAL_DUMP="$SRC"
fi

# Optional GPG decrypt.
if [[ "$LOCAL_DUMP" == *.gpg ]]; then
  _log "Decrypting GPG bundle…"
  gpg --batch --yes --output "${LOCAL_DUMP%.gpg}" --decrypt "$LOCAL_DUMP"
  LOCAL_DUMP="${LOCAL_DUMP%.gpg}"
fi

# ── Restore ───────────────────────────────────────────────────────────
_log "Restoring $LOCAL_DUMP into $(_safe_db_url "$TARGET_DB_URL")…"
START=$(date +%s)

# We use `--clean --if-exists` so a re-run replaces existing rows; the
# target DB is expected to be either empty or a scratch DB.
pg_restore \
  --clean --if-exists \
  --no-owner --no-privileges \
  --dbname "$TARGET_DB_URL" \
  --verbose \
  "$LOCAL_DUMP"

END=$(date +%s)
_log "Restore complete in $((END - START))s."

# Sanity row count check on a known table — caller can verify more.
ROWCOUNT=$(psql "$TARGET_DB_URL" -tAc "SELECT COUNT(*) FROM htx_user")
_log "Sanity: htx_user has $ROWCOUNT rows."

_append_incident_log "RESTORE_OK" "duration=$((END - START))s htx_user=$ROWCOUNT"
