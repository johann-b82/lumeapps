#!/usr/bin/env bash
# Guard D (SSE-05): Confirms the --workers 1 invariant is preserved in all
# three required locations:
#
#   1. docker-compose.yml   — uvicorn command uses --workers 1
#   2. signage_pg_listen.py — contains the "--workers 1 INVARIANT" comment
#   3. signage_broadcast.py — references --workers 1 (any comment or string)
#
# WHY: The asyncpg LISTEN/NOTIFY connection and the in-process fanout dict
# (_device_queues) are per-process state. If --workers > 1, each worker has
# its own listener and queue — SSE events become non-deterministic (race
# between which worker handles the SSE connection vs which worker's listener
# fired). This is a cross-cutting hazard (#4) locked for all v1.22 phases.
#
# Usage: bash scripts/ci/check_workers_one_invariant.sh
#   (Does not require docker compose — reads source files directly)
set -euo pipefail

COMPOSE_FILE="docker-compose.yml"
PG_LISTEN_FILE="backend/app/services/signage_pg_listen.py"
BROADCAST_FILE="backend/app/services/signage_broadcast.py"

failures=()

# Check 1: docker-compose.yml uvicorn command
if [ ! -f "$COMPOSE_FILE" ]; then
  failures+=("$COMPOSE_FILE not found")
elif ! grep -qE "uvicorn.*--workers 1" "$COMPOSE_FILE"; then
  failures+=("$COMPOSE_FILE: missing 'uvicorn ... --workers 1' in uvicorn command")
fi

# Check 2: signage_pg_listen.py INVARIANT comment
if [ ! -f "$PG_LISTEN_FILE" ]; then
  failures+=("$PG_LISTEN_FILE not found")
elif ! grep -q -- "--workers 1 INVARIANT" "$PG_LISTEN_FILE"; then
  failures+=("$PG_LISTEN_FILE: missing '--workers 1 INVARIANT' comment")
fi

# Check 3: signage_broadcast.py workers reference
if [ ! -f "$BROADCAST_FILE" ]; then
  failures+=("$BROADCAST_FILE not found")
elif ! grep -q -- "--workers 1" "$BROADCAST_FILE"; then
  failures+=("$BROADCAST_FILE: missing '--workers 1' reference")
fi

if [ "${#failures[@]}" -gt 0 ]; then
  echo "FAIL: Guard D — --workers 1 invariant violated (SSE-05, cross-cutting hazard #4)"
  for f in "${failures[@]}"; do
    echo "  - $f"
  done
  echo ""
  echo "  The --workers 1 constraint is LOCKED for v1.22. The asyncpg LISTEN/NOTIFY"
  echo "  connection and signage fanout dict are per-process. Multiple workers cause"
  echo "  non-deterministic SSE delivery."
  echo "  Do NOT remove or change --workers 1 without a full SSE architecture review."
  exit 1
fi

echo "PASS: Guard D — --workers 1 invariant preserved in all 3 locations"
