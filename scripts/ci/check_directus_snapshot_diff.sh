#!/usr/bin/env bash
# Guard B (SCHEMA-03 Directus metadata half): `directus schema snapshot` output
# must be diff-free against the committed directus/snapshots/v1.22.yaml.
#
# Directus maintains its own metadata layer (fields, relations, collections) on
# top of the Postgres schema. Guard A checks the DDL; Guard B checks the Directus
# metadata. Both must be in sync to prevent UI or API regressions.
#
# If this fails in CI it means someone changed Directus field metadata (display
# options, interface settings, relations) without committing an updated snapshot.
#
# To regenerate the committed snapshot after an intentional change:
#   docker compose exec directus npx directus schema snapshot -y /directus/snapshots/v1.22.yaml
#   # Then commit the updated file
#
# Usage: bash scripts/ci/check_directus_snapshot_diff.sh
#   (Requires: docker compose up -d with directus healthy)
set -euo pipefail

COMMITTED_SNAPSHOT="directus/snapshots/v1.22.yaml"
CURRENT_SNAPSHOT="/tmp/kpi-current-snapshot-$$.yaml"

if [ ! -f "$COMMITTED_SNAPSHOT" ]; then
  echo "ERROR: committed snapshot not found: $COMMITTED_SNAPSHOT"
  echo "  Create it with: docker compose exec directus npx directus schema snapshot -y /directus/snapshots/v1.22.yaml"
  exit 1
fi

# Capture the current Directus schema snapshot to a temp file
docker compose exec -T directus npx directus schema snapshot - > "$CURRENT_SNAPSHOT" 2>/dev/null

# Compare
if ! diff -u "$COMMITTED_SNAPSHOT" "$CURRENT_SNAPSHOT"; then
  echo ""
  echo "FAIL: Guard B — Directus snapshot diff vs committed YAML (SCHEMA-03)"
  echo "  The lines above show what changed in Directus metadata."
  echo ""
  echo "  If the change is intentional:"
  echo "    1. docker compose exec directus npx directus schema snapshot -y /directus/snapshots/v1.22.yaml"
  echo "    2. Commit the updated directus/snapshots/v1.22.yaml"
  echo "    3. If the change also involves a DB column: run make schema-fixture-update"
  rm -f "$CURRENT_SNAPSHOT"
  exit 1
fi

rm -f "$CURRENT_SNAPSHOT"
echo "PASS: Guard B — Directus snapshot matches committed YAML (schema drift: none)"
