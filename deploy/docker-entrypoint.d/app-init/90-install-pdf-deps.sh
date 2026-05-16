#!/bin/bash
# TrainPlex Step 7.4 — install PDF-rendering deps at container start.
#
# Reportlab is a pure-Python PDF generator (no native deps). We pip-install
# it on every boot; pip is a no-op if the wheel is already present. Total
# cold-start cost is ~2s; warm-start cost is <500ms.
#
# Rationale (plan Step 7.4 + 7.7): we need branded PDF export for
#   - founder weekly snapshot
#   - leaderboard (period: weekly|monthly)
#   - cohort retention analyzer
#   - per-project ROI (investor/client share)
# without rebuilding the base image.

set -e ${DEBUG:+-x}

PIP_BIN="/label-studio/.venv/bin/pip"

if [ ! -x "$PIP_BIN" ]; then
  echo "[trainplex] $0: $PIP_BIN not found, skipping PDF deps install" >&3
  exit 0
fi

# --disable-pip-version-check avoids noisy stderr that the entrypoint
# wrapper sometimes flags. --quiet keeps boot logs clean. reportlab is
# pinned to the major version we tested with (4.x).
"$PIP_BIN" install --quiet --disable-pip-version-check \
  'reportlab>=4.0,<5.0' >&3 2>&1 || {
  echo "[trainplex] $0: reportlab install failed, PDF endpoints will fall back to minimal renderer" >&3
}

# Verify the import works; the renderer self-probes too but a boot-time
# log makes ops feedback faster.
if "$PIP_BIN" show reportlab >/dev/null 2>&1; then
  RL_VER=$("$PIP_BIN" show reportlab 2>/dev/null | awk '/^Version:/ {print $2}')
  echo "[trainplex] $0: reportlab ${RL_VER} ready — branded PDF renderer active" >&3
else
  echo "[trainplex] $0: reportlab NOT installed — using minimal PDF fallback" >&3
fi
