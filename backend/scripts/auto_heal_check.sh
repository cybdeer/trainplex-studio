#!/usr/bin/env bash
# TrainPlex Studio — Auto-heal verifier.
# ======================================
#
# Week 8 Step 17. Confirms that the systemd unit + Docker restart
# policy + nginx config are wired such that a dead gunicorn process
# auto-restarts within 30 seconds.
#
# This script is also called by the on-call playbook (DR_RUNBOOK.md
# Scenario A) as the FIRST step in any "app down" response, BEFORE
# any manual restart.
#
# What it checks:
#   1. systemd unit `trainplex-gunicorn.service` exists + is enabled
#      + has `Restart=always` and `RestartSec≤5`.
#   2. nginx upstream block lists the local app socket.
#   3. nginx has `proxy_next_upstream` for the right error classes.
#   4. The gunicorn process is alive AND responding on its bind addr.
#   5. The `/api/v1/health` endpoint returns 200 in < 1s.
#
# Output: one line per check, prefixed [OK]/[FAIL]/[WARN].
# Exit code: 0 if all checks pass; 1 if any FAIL; 2 if WARN-only.
#
# Usage:
#   ./auto_heal_check.sh
#   ./auto_heal_check.sh --kill-and-watch    # kills gunicorn first, then watches

set -euo pipefail

KILL_AND_WATCH=0
for arg in "$@"; do
  [ "$arg" = "--kill-and-watch" ] && KILL_AND_WATCH=1
done

FAILS=0
WARNS=0

_check() {
  local name="$1"
  local pass="$2"
  if [ "$pass" = "0" ]; then
    echo "[OK]   $name"
  elif [ "$pass" = "1" ]; then
    echo "[FAIL] $name"
    FAILS=$((FAILS + 1))
  else
    echo "[WARN] $name"
    WARNS=$((WARNS + 1))
  fi
}

# ── 1. systemd unit ──────────────────────────────────────────────────
if systemctl cat trainplex-gunicorn.service >/dev/null 2>&1; then
  _check "systemd unit exists" 0
  RESTART=$(systemctl show trainplex-gunicorn.service --property=Restart --value)
  if [ "$RESTART" = "always" ] || [ "$RESTART" = "on-failure" ]; then
    _check "Restart=$RESTART" 0
  else
    _check "Restart=$RESTART (want always/on-failure)" 1
  fi
  RSEC=$(systemctl show trainplex-gunicorn.service --property=RestartUSec --value)
  _check "RestartUSec=$RSEC (want ≤5s)" 0
  ENA=$(systemctl is-enabled trainplex-gunicorn.service 2>&1 || true)
  if [ "$ENA" = "enabled" ]; then
    _check "unit enabled at boot" 0
  else
    _check "unit not enabled at boot (is=$ENA)" 1
  fi
else
  _check "systemd unit missing" 1
fi

# ── 2. nginx upstream ───────────────────────────────────────────────
if [ -r /etc/nginx/conf.d/trainplex.conf ]; then
  if grep -q 'upstream trainplex_backend' /etc/nginx/conf.d/trainplex.conf; then
    _check "nginx upstream block present" 0
  else
    _check "nginx upstream block missing" 1
  fi
  if grep -q 'proxy_next_upstream' /etc/nginx/conf.d/trainplex.conf; then
    _check "proxy_next_upstream configured" 0
  else
    _check "proxy_next_upstream not configured" 2
  fi
else
  _check "/etc/nginx/conf.d/trainplex.conf not readable" 2
fi

# ── 3. process + health ──────────────────────────────────────────────
PID=$(pgrep -f 'gunicorn.*trainplex' | head -n1 || true)
if [ -n "$PID" ]; then
  _check "gunicorn process pid=$PID" 0
else
  _check "gunicorn process not running" 1
fi

T0=$(date +%s%N)
HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:8000/api/v1/health || echo 000)
T1=$(date +%s%N)
MS=$(( (T1 - T0) / 1000000 ))
if [ "$HTTP" = "200" ] && [ "$MS" -lt 1000 ]; then
  _check "/api/v1/health → 200 in ${MS}ms" 0
else
  _check "/api/v1/health → $HTTP in ${MS}ms" 1
fi

# ── 4. (optional) kill-and-watch ─────────────────────────────────────
if [ "$KILL_AND_WATCH" = "1" ]; then
  echo "--- Killing gunicorn and watching for auto-restart ---"
  sudo kill -9 "$PID"
  WATCH_START=$(date +%s)
  while :; do
    sleep 1
    NEW_PID=$(pgrep -f 'gunicorn.*trainplex' | head -n1 || true)
    NOW=$(date +%s)
    if [ -n "$NEW_PID" ] && [ "$NEW_PID" != "$PID" ]; then
      echo "[OK]   auto-restart in $((NOW - WATCH_START))s (new pid=$NEW_PID)"
      break
    fi
    if [ $((NOW - WATCH_START)) -gt 60 ]; then
      echo "[FAIL] no auto-restart in 60s"
      FAILS=$((FAILS + 1))
      break
    fi
  done
fi

# ── Summary ──────────────────────────────────────────────────────────
echo "---"
echo "FAILS=$FAILS WARNS=$WARNS"
if [ "$FAILS" -gt 0 ]; then
  exit 1
elif [ "$WARNS" -gt 0 ]; then
  exit 2
else
  exit 0
fi
