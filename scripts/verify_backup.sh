#!/usr/bin/env bash
# TrainPlex Studio — Backup Verifier.
# ===================================
#
# Week 8 Step 11. Nightly: pull the latest backup, restore it into a
# scratch DB, count critical rows, smoke-check, then drop the scratch
# DB. Reports green/red to incident log so the founder always knows
# the backups are restorable.
#
# What this script does:
#   1. Resolve `LATEST_BACKUP` (env var or `b2://trainplex-backups/latest.dump`).
#   2. Create a scratch DB on `$VERIFY_HOST` (defaults to localhost).
#   3. Restore into scratch via `restore_db.sh`.
#   4. Count `htx_user`, `project`, `task`, `task_completion`,
#      `htx_wa_broadcast_log`, `htx_quality_alert`.
#   5. Compare against the previous night's counts (stored in
#      `${VERIFY_STATE_DIR}/last_counts.json`); flag anomalies.
#   6. Drop the scratch DB.
#   7. Append the result to INCIDENT_LOG.
#
# Designed to be cron-friendly: exits 0 on full success, 1 on count
# regression, 2 on outright restore failure. Stderr carries the
# detail; stdout is a single-line summary.
#
# Usage:
#   ./verify_backup.sh                       # use $LATEST_BACKUP
#   ./verify_backup.sh /backups/foo.dump
#
# Founder rule: no personal mobile, append to incident log.

set -euo pipefail

LATEST_BACKUP="${1:-${LATEST_BACKUP:-/backups/trainplex-prod-latest.dump}}"
VERIFY_HOST="${VERIFY_HOST:-localhost}"
VERIFY_PORT="${VERIFY_PORT:-5432}"
VERIFY_USER="${VERIFY_USER:-postgres}"
VERIFY_STATE_DIR="${VERIFY_STATE_DIR:-/var/lib/trainplex-data/verify}"
INCIDENT_LOG="${INCIDENT_LOG:-/var/lib/trainplex-data/INCIDENT_LOG.md}"

SCRATCH_DB="trainplex_verify_$(date +%s)"

mkdir -p "$VERIFY_STATE_DIR"

_log() {
  echo "[$(date -u +%FT%TZ)] [verify_backup] $*" >&2
}

_append_incident_log() {
  local kind="$1"
  local detail="$2"
  mkdir -p "$(dirname "$INCIDENT_LOG")"
  {
    echo
    echo "## $(date -u +%FT%TZ) — ${kind}"
    echo "* script: verify_backup.sh"
    echo "* backup: ${LATEST_BACKUP}"
    echo "* detail: ${detail}"
  } >> "$INCIDENT_LOG"
}

# ── Step 1: create scratch DB ────────────────────────────────────────
_log "Creating scratch DB ${SCRATCH_DB} on ${VERIFY_HOST}:${VERIFY_PORT}"
psql -h "$VERIFY_HOST" -p "$VERIFY_PORT" -U "$VERIFY_USER" -c \
  "CREATE DATABASE ${SCRATCH_DB} WITH ENCODING 'UTF8'" >/dev/null

trap 'psql -h "$VERIFY_HOST" -p "$VERIFY_PORT" -U "$VERIFY_USER" -c "DROP DATABASE IF EXISTS ${SCRATCH_DB}" >/dev/null 2>&1 || true' EXIT

SCRATCH_URL="postgres://${VERIFY_USER}@${VERIFY_HOST}:${VERIFY_PORT}/${SCRATCH_DB}"

# ── Step 2: restore ──────────────────────────────────────────────────
_log "Restoring ${LATEST_BACKUP}…"
START=$(date +%s)
if ! TARGET_DB_URL="$SCRATCH_URL" \
  BACKUP_DRY_RUN="${BACKUP_DRY_RUN:-0}" \
  bash "$(dirname "$0")/restore_db.sh" "$LATEST_BACKUP" >/dev/null 2>&1; then
  _log "FAIL: restore returned non-zero"
  echo "VERIFY_FAIL: restore non-zero exit"
  _append_incident_log "VERIFY_RESTORE_FAIL" "could not restore $LATEST_BACKUP"
  exit 2
fi
RESTORE_SEC=$(( $(date +%s) - START ))
_log "Restored in ${RESTORE_SEC}s"

# ── Step 3: row counts ───────────────────────────────────────────────
declare -A COUNTS
for table in htx_user project task task_completion htx_wa_broadcast_log htx_quality_alert; do
  n=$(psql "$SCRATCH_URL" -tAc "SELECT COUNT(*) FROM ${table}" 2>/dev/null || echo 0)
  COUNTS[$table]=$n
  _log "table ${table} rows=${n}"
done

# ── Step 4: diff vs previous ─────────────────────────────────────────
PREV_FILE="${VERIFY_STATE_DIR}/last_counts.json"
ALERT=""
if [ -f "$PREV_FILE" ]; then
  while IFS= read -r line; do
    key=$(echo "$line" | cut -d: -f1)
    prev=$(echo "$line" | cut -d: -f2)
    cur=${COUNTS[$key]:-0}
    # A drop of more than 10% on any critical table is suspicious; a drop
    # of more than 0 on htx_user is *always* suspicious (we don't delete
    # users).
    if [ "$key" = "htx_user" ] && [ "$cur" -lt "$prev" ]; then
      ALERT+="${key}_dropped(${prev}→${cur}) "
    fi
    if [ "$prev" -gt 0 ] && [ "$cur" -lt $((prev * 90 / 100)) ]; then
      ALERT+="${key}_lt_90pct(${prev}→${cur}) "
    fi
  done < "$PREV_FILE"
fi

# Persist current counts.
: > "$PREV_FILE"
for k in "${!COUNTS[@]}"; do
  echo "${k}:${COUNTS[$k]}" >> "$PREV_FILE"
done

# ── Step 5: smoke ────────────────────────────────────────────────────
# Spot check — pick one trainer and read their last 5 task_completions.
SAMPLE=$(psql "$SCRATCH_URL" -tAc \
  "SELECT u.email, COUNT(tc.id) FROM htx_user u
   LEFT JOIN task_completion tc ON tc.completed_by_id = u.id
   WHERE u.role='trainer'
   GROUP BY u.email
   ORDER BY 2 DESC LIMIT 1" 2>/dev/null || echo "no_trainers")
_log "spot-check top trainer: ${SAMPLE}"

# ── Summary ──────────────────────────────────────────────────────────
SUMMARY="rows: htx_user=${COUNTS[htx_user]} project=${COUNTS[project]} task=${COUNTS[task]} restore=${RESTORE_SEC}s"
if [ -n "$ALERT" ]; then
  echo "VERIFY_REGRESSION: ${ALERT}"
  _append_incident_log "VERIFY_REGRESSION" "${SUMMARY} alerts=${ALERT}"
  exit 1
fi

echo "VERIFY_OK: ${SUMMARY}"
_append_incident_log "VERIFY_OK" "${SUMMARY}"
exit 0
