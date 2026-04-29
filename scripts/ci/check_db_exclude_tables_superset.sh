#!/usr/bin/env bash
# Guard C (SCHEMA-04): DB_EXCLUDE_TABLES in docker-compose.yml must be a
# superset of the hard-coded "never expose" allowlist.
#
# These tables must NEVER be exposed through Directus:
#   alembic_version, app_settings, personio_attendance, personio_absences,
#   personio_sync_meta, sensors, sensor_readings, sensor_poll_log,
#   signage_pairing_sessions, signage_heartbeat_event, upload_batches
#
# If any of these tables are removed from DB_EXCLUDE_TABLES, this guard fails.
# This prevents accidental exposure of internal/sensitive tables through the
# Directus admin UI or API.
#
# Usage: bash scripts/ci/check_db_exclude_tables_superset.sh
#   (Does not require docker compose — reads docker-compose.yml directly)
set -euo pipefail

COMPOSE_FILE="docker-compose.yml"

# Hard-coded never-expose allowlist (SCHEMA-04).
# Source: 65-PLAN.md interfaces section + STATE.md cross-cutting hazard #10.
NEVER_EXPOSE=(
  alembic_version
  app_settings
  personio_attendance
  personio_absences
  personio_sync_meta
  sensors
  sensor_readings
  sensor_poll_log
  signage_pairing_sessions
  signage_heartbeat_event
  upload_batches
)

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "ERROR: $COMPOSE_FILE not found in current directory."
  echo "  Run this script from the repository root."
  exit 1
fi

# Extract the DB_EXCLUDE_TABLES value from docker-compose.yml.
# Handles both "key: value" and "key=value" formats, with or without quotes.
# Comment lines (starting with optional whitespace + #) are excluded.
ENV_VALUE=$(grep -E "^\s+DB_EXCLUDE_TABLES" "$COMPOSE_FILE" | grep -v '^\s*#' | head -1 \
  | sed -E 's/.*DB_EXCLUDE_TABLES[=:][[:space:]]*//' \
  | sed -E 's/^["\x27]//; s/["\x27][[:space:]]*$//' \
  | tr -d '"' \
  | tr -d "'" \
  | tr -d '[:space:]')

if [ -z "$ENV_VALUE" ]; then
  echo "FAIL: Guard C — DB_EXCLUDE_TABLES not found in $COMPOSE_FILE (SCHEMA-04)"
  echo "  Add DB_EXCLUDE_TABLES to the api service environment in docker-compose.yml."
  exit 1
fi

missing=()
for table in "${NEVER_EXPOSE[@]}"; do
  # Check for exact table name match (comma-separated list, any position)
  if ! echo "$ENV_VALUE" | grep -qE "(^|,)${table}(,|$)"; then
    missing+=("$table")
  fi
done

if [ "${#missing[@]}" -gt 0 ]; then
  echo "FAIL: Guard C — DB_EXCLUDE_TABLES missing required never-expose entries (SCHEMA-04)"
  echo "  missing: ${missing[*]}"
  echo ""
  echo "  Current DB_EXCLUDE_TABLES value: $ENV_VALUE"
  echo ""
  echo "  Add the missing table(s) to DB_EXCLUDE_TABLES in docker-compose.yml."
  echo "  These tables must never be exposed through Directus."
  exit 1
fi

echo "PASS: Guard C — DB_EXCLUDE_TABLES is superset of never-expose allowlist (${#NEVER_EXPOSE[@]} tables checked)"
