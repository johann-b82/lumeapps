#!/usr/bin/env bash
# Phase 7 rebuild persistence smoke test (D-23).
#
# Verifies all settings (6 colors, app_name, default_language, logo bytes)
# survive a full `docker compose down` + `docker compose up --build` cycle,
# preserving the postgres_data named volume.
#
# Usage: ./scripts/smoke-rebuild.sh
# Exit 0 on success, non-zero + failing-step log on failure.
#
# Prereqs:
#   - Docker + Docker Compose v2.17+ (`--wait` support)
#   - Node available on host for `npx playwright test`
#   - `cd frontend && npx playwright install chromium` run once
set -euo pipefail

log() { printf '\n\033[1;34m[smoke-rebuild]\033[0m %s\n' "$*"; }
die() { printf '\n\033[1;31m[smoke-rebuild FAIL]\033[0m %s\n' "$*" >&2; exit 1; }

# Poll the api /health endpoint until it responds (up to ~90s).
# We use this instead of `docker compose up --wait` because some sandboxed
# environments SIGKILL the `--wait` form mid-handshake. Plain `up -d` + HTTP
# poll is equivalent but robust.
wait_for_api() {
  for i in $(seq 1 90); do
    if curl -sf -o /dev/null http://localhost:8000/health; then
      printf ' api ready (%ss)\n' "$i"
      return 0
    fi
    printf '.'
    sleep 1
  done
  die "api /health never came up (90s timeout)"
}

cleanup() {
  log "Cleanup: resetting app_settings singleton to defaults..."
  # Best-effort — run even if earlier steps failed. Non-fatal here so the
  # trap doesn't mask the original error code.
  docker compose exec -T api pytest tests/test_rebuild_cleanup.py -q || true
}
trap cleanup EXIT

# Step 1-2: bring the stack up, preserving postgres_data
log "Starting stack (preserves postgres_data)..."
docker compose up -d
wait_for_api

# Step 3: seed known state via pytest inside the api container
log "Seeding test state (8 fields + 1x1 red PNG)..."
docker compose exec -T api pytest tests/test_rebuild_seed.py -q \
  || die "Seed step failed"

# Step 4: stop containers WITHOUT -v (postgres_data must survive).
# --remove-orphans drops any stray compose containers that a prior partial
# up/down left behind, avoiding "container name already in use" on re-run.
# Also force-remove any still-present "Created" containers — on some Docker
# Desktop versions, a killed `up --wait` leaves container objects in Created
# state that `down` does not always clean up.
log "Stopping containers (volume persists)..."
docker compose down --remove-orphans
docker ps -aq --filter 'name=acm-kpi-light-' | xargs -r docker rm -f >/dev/null 2>&1 || true
# NOT 'down -v' — Pitfall 4: -v would nuke postgres_data and mask the bug.

# Step 5-6: rebuild images, then bring the stack up and wait for health.
# Split into two steps: on some Docker Desktop versions, combining `--build`
# with `--wait` races the frontend container creation against the image
# export and fails with "container name already in use".
log "Rebuilding images..."
docker compose build

# Starting the rebuilt stack: some Docker Desktop versions briefly leak
# ghost container objects after a `down`, so `up -d` can hit a transient
# "name already in use" conflict on the first try. Retry once after a
# forced cleanup — the second attempt reliably succeeds.
log "Starting rebuilt stack..."
if ! docker compose up -d 2>&1 | tee /tmp/smoke-up.log; then
  if grep -q "already in use" /tmp/smoke-up.log; then
    log "Ghost container conflict — force-removing and retrying..."
    docker ps -aq --filter 'name=acm-kpi-light-' | xargs -r docker rm -f >/dev/null 2>&1 || true
    docker compose up -d || die "Rebuild up failed on retry"
  else
    die "Rebuild up failed"
  fi
fi
wait_for_api

# Step 7: assert persistence via a fresh pytest session
log "Asserting DB persistence after rebuild..."
docker compose exec -T api pytest tests/test_rebuild_assert.py -q \
  || die "Assert step failed — state did not survive rebuild"

# Step 8: Playwright visual assertion from the host.
# The frontend container has no healthcheck — `--wait` only blocks on it
# being "running", not on Vite dev server actually serving HTTP. Poll the
# root path until it responds (or give up after ~60s).
log "Waiting for Vite dev server on :5173..."
for i in $(seq 1 60); do
  if curl -sf -o /dev/null http://localhost:5173/; then
    printf ' ready (%ss)\n' "$i"
    break
  fi
  printf '.'
  sleep 1
  if [ "$i" -eq 60 ]; then
    die "Vite dev server never came up on :5173"
  fi
done

log "Running Playwright visual check..."
( cd frontend && npx playwright test tests/e2e/rebuild-persistence.spec.ts ) \
  || die "Playwright visual check failed"

# Step 9: locale key parity (host Python — frontend files are not bind-mounted
# into the api container, Pitfall 6)
log "Checking locale key parity (en.json vs de.json)..."
python3 -c "
import json, sys
e = set(json.load(open('frontend/src/locales/en.json')))
d = set(json.load(open('frontend/src/locales/de.json')))
diff = e ^ d
if diff:
    print('Locale parity mismatch:', sorted(diff))
    sys.exit(1)
" || die "Locale key-parity check failed"

log "✓ Rebuild persistence verified"
