#!/usr/bin/env bash
# backend/scripts/build_app.sh — Wave-19 W2-CLEANUP MINOR-2
#
# Build the TrainPlex Studio production image with image-provenance labels
# baked in so `docker inspect` can answer "which git SHA + when" at runtime
# without rebuilding.
#
# Usage:
#   ./backend/scripts/build_app.sh                  # build with current HEAD
#   GIT_SHA=abc1234 ./backend/scripts/build_app.sh  # override SHA
#
# Outputs:
#   - `docker compose build --build-arg GIT_SHA=… --build-arg BUILD_TIME=…`
#   - prints `docker inspect` label block after success for verification
#
# Constraints honoured:
#   - Does NOT push to remote
#   - Does NOT commit credentials
#   - No founder-mobile literal anywhere (MEMORY rule)
set -euo pipefail

cd "$(dirname "$0")/../.."

GIT_SHA="${GIT_SHA:-$(git rev-parse --short HEAD)}"
BUILD_TIME="${BUILD_TIME:-$(date -Iseconds)}"

echo "==> Building trainplex-studio:prod"
echo "    GIT_SHA   = ${GIT_SHA}"
echo "    BUILD_TIME= ${BUILD_TIME}"

docker compose build \
    --build-arg GIT_SHA="${GIT_SHA}" \
    --build-arg BUILD_TIME="${BUILD_TIME}" \
    app

echo
echo "==> Verifying labels on trainplex-studio:prod"
docker inspect trainplex-studio:prod --format '{{json .Config.Labels}}' | python3 -m json.tool
