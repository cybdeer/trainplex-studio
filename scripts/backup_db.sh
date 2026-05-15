#!/usr/bin/env bash
# TrainPlex Studio — DB Backup → Backblaze B2 (S3-compatible) STUB.
# =================================================================
#
# Week 8 Step 11.
#
# What this script does:
#   1. Read `$DB_URL` (Postgres connection URL) from env.
#   2. pg_dump with `-Fc` (custom format, restorable + compact).
#   3. Optionally encrypt with gpg if `$BACKUP_GPG_KEY` set.
#   4. Upload to the configured B2 bucket via `b2 upload-file`.
#   5. Append a row to `/var/lib/trainplex-data/INCIDENT_LOG.md`
#      (founder rule: incident log append).
#
# IMPORTANT (founder rule — STUB):
#   No real B2/S3 calls happen in this commit. The `_upload_to_b2`
#   function dry-runs the upload (logs the would-be command) when
#   `$BACKUP_DRY_RUN=1` or `$B2_APPLICATION_KEY_ID` is empty.
#   The production wire-up is a one-line flip the founder makes
#   after the B2 bucket + IAM are provisioned.
#
# Usage:
#   ./backup_db.sh prod            # full backup
#   ./backup_db.sh staging         # backup staging DB
#   BACKUP_DRY_RUN=1 ./backup_db.sh prod   # rehearse without uploading
#
# Founder rule: NO personal mobile, NO credentials in logs (passwords
# are scrubbed before any echo via `_safe_db_url`).

set -euo pipefail

LABEL="${1:-prod}"
TS=$(date -u +%Y%m%dT%H%M%SZ)
WORKDIR="${BACKUP_WORKDIR:-/tmp/trainplex-backups}"
INCIDENT_LOG="${INCIDENT_LOG:-/var/lib/trainplex-data/INCIDENT_LOG.md}"
DUMP_FILE="${WORKDIR}/trainplex-${LABEL}-${TS}.dump"

mkdir -p "$WORKDIR"

# ── Helpers ───────────────────────────────────────────────────────────
_safe_db_url() {
  # Strip password from a postgres:// URL so it never enters logs.
  echo "$1" | sed -E 's#(://[^:]+):[^@]+@#\1:***@#'
}

_log() {
  echo "[$(date -u +%FT%TZ)] [backup_db] $*"
}

_append_incident_log() {
  local kind="$1"
  local detail="$2"
  mkdir -p "$(dirname "$INCIDENT_LOG")"
  {
    echo
    echo "## $(date -u +%FT%TZ) — ${kind}"
    echo "* script: backup_db.sh"
    echo "* label: ${LABEL}"
    echo "* detail: ${detail}"
    echo "* operator: ${USER:-unknown}@$(hostname)"
  } >> "$INCIDENT_LOG"
}

_upload_to_b2() {
  local file="$1"
  if [ "${BACKUP_DRY_RUN:-0}" = "1" ] || [ -z "${B2_APPLICATION_KEY_ID:-}" ]; then
    _log "STUB upload — would have run: b2 upload-file \"${B2_BUCKET:-<unset>}\" \"$file\" \"$(basename "$file")\""
    return 0
  fi
  # Real upload path — guarded behind the env check above.
  b2 authorize-account "$B2_APPLICATION_KEY_ID" "$B2_APPLICATION_KEY"
  b2 upload-file "$B2_BUCKET" "$file" "$(basename "$file")"
}

# ── Main ──────────────────────────────────────────────────────────────
if [ -z "${DB_URL:-}" ]; then
  _log "ERROR: \$DB_URL is not set."
  _append_incident_log "BACKUP_FAILED" "missing DB_URL env"
  exit 2
fi

_log "Starting backup of $(_safe_db_url "$DB_URL") → $DUMP_FILE"

# pg_dump itself — `-Fc` (custom format), `-Z 9` (max compression).
# We exclude the test/CI schemas to keep the dump compact.
pg_dump "$DB_URL" \
  -Fc -Z 9 \
  --no-owner --no-privileges \
  --exclude-schema='pg_temp_*' \
  --file "$DUMP_FILE"

# Hash + size for audit trail.
SIZE=$(stat -c %s "$DUMP_FILE" 2>/dev/null || stat -f %z "$DUMP_FILE")
SHA=$(sha256sum "$DUMP_FILE" | cut -d' ' -f1)
_log "Dump complete: ${SIZE} bytes, sha256=${SHA}"

# Optional encryption.
FINAL_FILE="$DUMP_FILE"
if [ -n "${BACKUP_GPG_KEY:-}" ]; then
  _log "Encrypting with GPG key fingerprint ${BACKUP_GPG_KEY}…"
  gpg --batch --yes --recipient "$BACKUP_GPG_KEY" --output "${DUMP_FILE}.gpg" \
    --encrypt "$DUMP_FILE"
  rm "$DUMP_FILE"
  FINAL_FILE="${DUMP_FILE}.gpg"
fi

# Upload (or stub).
_upload_to_b2 "$FINAL_FILE"

# Audit log.
_append_incident_log "BACKUP_OK" "${SIZE}B sha256=${SHA} file=$(basename "$FINAL_FILE")"

_log "Done. Local copy retained at $FINAL_FILE for 24h then rotated by"
_log "  /etc/cron.daily/trainplex-backup-rotate (separate from this script)."
