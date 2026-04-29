#!/bin/sh
# apply-snapshot-idempotent.sh — wrap `directus schema apply` so it tolerates
# the Directus 11 #25760 "Collection already exists" failure on warm DBs.
#
# Why this script exists:
#   On first cold boot, Directus auto-introspects every Postgres table not in
#   DB_EXCLUDE_TABLES and registers it as a collection (with default metadata
#   only — no `note`, `hidden=false`, etc.). When `directus schema apply` then
#   runs the snapshot, it tries to *create* those same collections via the
#   internal `createCollections` path, which 400s with
#   "Invalid payload. Collection X already exists." The container exits 1
#   and downstream services (bootstrap-roles, api, frontend) never start.
#
# Strategy:
#   1. Try `directus schema apply --yes` once. Cold-boot path on a truly empty
#      DB succeeds and we exit 0.
#   2. If it fails with the "already exists" signature, run the bundled Node
#      fallback (`apply-snapshot-fallback.mjs`) which logs in as admin and
#      PATCHes /collections/{name} for each top-level collection in the YAML
#      to apply our metadata tweaks. PATCH is idempotent.
#   3. If the failure signature is different, surface the error and exit
#      non-zero — that's a real problem worth blocking startup for.
#
# Idempotency:
#   - The full script is safe to re-run on any DB state.
#   - Permission rows are still created by bootstrap-roles.sh; this script
#     only touches collection metadata.
#
# References:
#   - https://github.com/directus/directus/issues/25760
#   - docs/operator-runbook.md § 13 (manual fallback recipe this script
#     automates).

set -eu

SNAPSHOT="${SNAPSHOT_FILE:-/snapshots/v1.22.yaml}"

log() { printf '[apply-snapshot] %s\n' "$*"; }

if [ ! -f "$SNAPSHOT" ]; then
  log "FATAL: snapshot file $SNAPSHOT not found"
  exit 2
fi

log "attempting: directus schema apply --yes $SNAPSHOT"
output=$(npx directus schema apply --yes "$SNAPSHOT" 2>&1) && rc=0 || rc=$?

if [ "$rc" -eq 0 ]; then
  printf '%s\n' "$output"
  log "schema apply succeeded"
  exit 0
fi

# Known-benign failure signatures. apply-diff in Directus 11.17 fails when
# the live DB doesn't match the snapshot's diff baseline:
#   - "already exists" (#25760): collection auto-introspected before apply.
#   - "doesn't exist": apply-diff tried to drop a collection the snapshot
#     no longer references (DB_EXCLUDE_TABLES) but the live DB never had it.
# Both are recoverable via REST metadata sync.
if ! printf '%s' "$output" | grep -qE "already exists|doesn't exist"; then
  log "schema apply failed with an unexpected error:"
  printf '%s\n' "$output" >&2
  exit "$rc"
fi

log "schema apply failed with a known apply-diff drift (already-exists / doesn't-exist) — falling back to REST metadata sync."

FALLBACK="$(dirname "$0")/apply-snapshot-fallback.mjs"
[ -f "$FALLBACK" ] || FALLBACK="/apply-snapshot-fallback.mjs"

node "$FALLBACK" "$SNAPSHOT"
