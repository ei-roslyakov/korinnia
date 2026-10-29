#!/bin/sh
# Performance check on a large synthetic tree (`make perf`, PEOPLE=2000 by default).
# Starts a throwaway production-build stack, generates the tree, measures the API and the
# browser (scripts/perf/browser.mjs), prints the numbers and removes the stack again.
set -eu
cd "$(dirname "$0")/.."
PEOPLE="${PEOPLE:-2000}"
PORT="${PERF_PORT:-8092}"
# `make perf` passes the Makefile's image (the one matching @playwright/test).
PLAYWRIGHT_IMAGE="${PLAYWRIGHT_IMAGE:-mcr.microsoft.com/playwright:v1.64.1-noble}"
STACK="docker compose -p korinnia-perf -f docker-compose.yml"

cleanup() { $STACK down -v --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT

HTTP_PORT=$PORT ENVIRONMENT=production DEMO_TREE_FOR_NEW_USERS=false \
  $STACK up -d --build --wait >/dev/null
line=$($STACK exec -T backend python -m app.perf --people "$PEOPLE" | tail -1)
echo "$line"
tree=$(echo "$line" | sed -n 's/.*(\([0-9a-f-]*\)).*/\1/p')

docker run --rm --network korinnia-perf_default -e BASE_URL=http://nginx -e TREE_ID="$tree" \
  -v "$PWD/scripts/perf:/perf:ro" -v korinnia-e2e-node-modules:/app/node_modules -w /app \
  "$PLAYWRIGHT_IMAGE" sh -c "cp /perf/browser.mjs /app/perf.mjs && node perf.mjs"
