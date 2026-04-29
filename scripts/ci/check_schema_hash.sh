#!/usr/bin/env bash
# Guard A (SCHEMA-03 DDL half): SHA256 of information_schema.columns for
# v1.22-surfaced tables vs committed directus/fixtures/schema-hash.txt.
#
# Any DDL drift (column added, removed, type changed, nullability changed)
# causes this guard to fail CI. This prevents silent schema mutations from
# slipping into production undetected.
#
# To regenerate the fixture after an intentional DDL change:
#   make schema-fixture-update
#
# Usage: bash scripts/ci/check_schema_hash.sh
#   (Requires: docker compose up -d with db healthy + alembic upgrade head run)
set -euo pipefail

# Source .env so POSTGRES_USER / POSTGRES_DB are available on the host shell
# (docker compose exec runs on host; the container's env isn't auto-inherited).
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

TABLES="'signage_devices','signage_playlists','signage_playlist_items','signage_device_tags','signage_playlist_tag_map','signage_device_tag_map','signage_schedules','sales_records','personio_employees'"

FIXTURE="directus/fixtures/schema-hash.txt"

if [ ! -f "$FIXTURE" ]; then
  echo "ERROR: schema hash fixture not found: $FIXTURE"
  echo "  Run: make schema-fixture-update"
  exit 1
fi

# Compute current hash from information_schema using MD5 (no pgcrypto extension required).
# We use md5() which is available in all PostgreSQL versions without extensions.
CURRENT=$(docker compose exec -T db psql \
  -U "${POSTGRES_USER:-kpi}" \
  -d "${POSTGRES_DB:-kpi}" \
  -tA -c "
    SELECT md5(string_agg(row_data, '|' ORDER BY row_data))
    FROM (
      SELECT concat_ws(',',
        table_name,
        column_name,
        data_type,
        is_nullable,
        coalesce(column_default, '')
      ) AS row_data
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name IN ($TABLES)
    ) s;
  " 2>/dev/null | tr -d '[:space:]')

EXPECTED=$(cat "$FIXTURE" | tr -d '[:space:]')

if [ -z "$CURRENT" ]; then
  echo "ERROR: could not compute current schema hash (empty result)"
  echo "  Ensure the database is running and alembic upgrade head has been applied."
  exit 1
fi

if [ "$CURRENT" != "$EXPECTED" ]; then
  echo "FAIL: Guard A — DDL hash mismatch (SCHEMA-03)"
  echo "  expected: $EXPECTED"
  echo "  actual:   $CURRENT"
  echo ""
  echo "  A column was added/removed/changed on a v1.22-surfaced table."
  echo "  If this change is intentional:"
  echo "    1. Apply the Alembic migration"
  echo "    2. Run: make schema-fixture-update"
  echo "    3. Commit directus/fixtures/schema-hash.txt"
  exit 1
fi

echo "PASS: Guard A — DDL hash matches fixture (schema drift: none)"
