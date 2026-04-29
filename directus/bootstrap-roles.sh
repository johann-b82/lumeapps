#!/bin/sh
# bootstrap-roles.sh — idempotent roles-as-code for Directus 11 via REST API.
#
# Replaces the v10-style snapshot.yml approach (Plan 02) which was rejected by
# Directus 11's stricter schema apply (policies/access tables and role↔policy
# decoupling introduced in v11 made the v10 snapshot shape invalid).
#
# Flow:
#   1. POST /auth/login           -> access_token
#   2. Ensure "Viewer Read" policy exists (fixed UUID)
#   3. Ensure "Viewer" role exists (fixed UUID)
#   4. Ensure access row links Viewer role <-> Viewer Read policy (fixed UUID)
#
# Admin role is NOT created here — Directus ships a built-in "Administrator"
# role (seeded by ADMIN_EMAIL/ADMIN_PASSWORD env bootstrap). Downstream code
# should key on the name "Administrator" for admin access.
#
# Re-running this script on a populated DB is a no-op (GET-before-POST).

set -eu

: "${DIRECTUS_URL:?DIRECTUS_URL not set}"
: "${DIRECTUS_ADMIN_EMAIL:?DIRECTUS_ADMIN_EMAIL not set}"
: "${DIRECTUS_ADMIN_PASSWORD:?DIRECTUS_ADMIN_PASSWORD not set}"

VIEWER_POLICY_ID="a2222222-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
VIEWER_ROLE_ID="a2222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
VIEWER_ACCESS_ID="a2222222-cccc-cccc-cccc-cccccccccccc"

log() { printf '[bootstrap-roles] %s\n' "$*"; }

# ensure_permission: GET-before-POST idempotent permission row creation.
# Args: $1=permission_id (fixed UUID), $2=collection, $3=action, $4=fields_json_array
ensure_permission() {
  pid="$1"; coll="$2"; act="$3"; fields="$4"
  status=$(api GET "/permissions/${pid}")
  if [ "$status" = "200" ]; then
    log "permission ${pid} (${coll}.${act}) exists — skipping"
    return 0
  fi
  log "creating permission ${pid} (${coll}.${act}) fields=${fields}"
  status=$(api POST "/permissions" "{
    \"id\":\"${pid}\",
    \"policy\":\"${VIEWER_POLICY_ID}\",
    \"collection\":\"${coll}\",
    \"action\":\"${act}\",
    \"fields\":${fields},
    \"permissions\":{}
  }")
  [ "$status" = "200" ] || [ "$status" = "204" ] || {
    log "ERROR: POST /permissions returned ${status}"; cat /tmp/api.body 2>/dev/null; exit 1
  }
}

# curl helper that prints body and captures HTTP status to a file descriptor.
# Usage: http_status=$(api GET /roles/xxx) ; body in /tmp/api.body
api() {
  method="$1"; path="$2"; body="${3:-}"
  if [ -n "$body" ]; then
    curl -sS -o /tmp/api.body -w '%{http_code}' \
      -X "$method" \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Content-Type: application/json" \
      --data "$body" \
      "${DIRECTUS_URL}${path}"
  else
    curl -sS -o /tmp/api.body -w '%{http_code}' \
      -X "$method" \
      -H "Authorization: Bearer ${TOKEN}" \
      "${DIRECTUS_URL}${path}"
  fi
}

log "Logging in as ${DIRECTUS_ADMIN_EMAIL} at ${DIRECTUS_URL}"
LOGIN_RESP=$(curl -sS -X POST \
  -H "Content-Type: application/json" \
  --data "{\"email\":\"${DIRECTUS_ADMIN_EMAIL}\",\"password\":\"${DIRECTUS_ADMIN_PASSWORD}\"}" \
  "${DIRECTUS_URL}/auth/login")

# crude token extraction — busybox sh + no jq available in directus image base.
# We pipe via python3 if present (directus image has node but not jq/python).
# Fall back to sed-based extraction.
TOKEN=$(printf '%s' "$LOGIN_RESP" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
if [ -z "$TOKEN" ]; then
  log "ERROR: failed to parse access_token from login response:"
  printf '%s\n' "$LOGIN_RESP"
  exit 1
fi
log "Login OK — token acquired"

# --- 1. Ensure Viewer Read policy ---
status=$(api GET "/policies/${VIEWER_POLICY_ID}")
if [ "$status" = "200" ]; then
  log "Viewer Read policy exists (${VIEWER_POLICY_ID}) — skipping"
elif [ "$status" = "403" ] || [ "$status" = "404" ]; then
  log "Creating Viewer Read policy (${VIEWER_POLICY_ID})"
  status=$(api POST "/policies" "{
    \"id\":\"${VIEWER_POLICY_ID}\",
    \"name\":\"Viewer Read\",
    \"icon\":\"visibility\",
    \"description\":\"Read-only dashboard access — no admin, no app access to private data.\",
    \"admin_access\":false,
    \"app_access\":true
  }")
  if [ "$status" != "200" ] && [ "$status" != "204" ]; then
    log "ERROR: creating policy returned HTTP ${status}"
    cat /tmp/api.body; exit 1
  fi
  log "Viewer Read policy created"
else
  log "ERROR: unexpected GET /policies status ${status}"
  cat /tmp/api.body; exit 1
fi

# --- 2. Ensure Viewer role ---
status=$(api GET "/roles/${VIEWER_ROLE_ID}")
if [ "$status" = "200" ]; then
  log "Viewer role exists (${VIEWER_ROLE_ID}) — skipping"
elif [ "$status" = "403" ] || [ "$status" = "404" ]; then
  log "Creating Viewer role (${VIEWER_ROLE_ID})"
  status=$(api POST "/roles" "{
    \"id\":\"${VIEWER_ROLE_ID}\",
    \"name\":\"Viewer\",
    \"icon\":\"visibility\",
    \"description\":\"Read-only dashboard access.\"
  }")
  if [ "$status" != "200" ] && [ "$status" != "204" ]; then
    log "ERROR: creating role returned HTTP ${status}"
    cat /tmp/api.body; exit 1
  fi
  log "Viewer role created"
else
  log "ERROR: unexpected GET /roles status ${status}"
  cat /tmp/api.body; exit 1
fi

# --- 3. Ensure access row linking Viewer role <-> Viewer Read policy ---
# The /access collection uses role+policy composite semantics in v11.
# We use a fixed UUID for the access row so re-runs are idempotent.
status=$(api GET "/access/${VIEWER_ACCESS_ID}")
if [ "$status" = "200" ]; then
  log "Viewer access row exists (${VIEWER_ACCESS_ID}) — skipping"
elif [ "$status" = "403" ] || [ "$status" = "404" ]; then
  log "Creating access row linking Viewer role <-> Viewer Read policy"
  status=$(api POST "/access" "{
    \"id\":\"${VIEWER_ACCESS_ID}\",
    \"role\":\"${VIEWER_ROLE_ID}\",
    \"policy\":\"${VIEWER_POLICY_ID}\",
    \"sort\":1
  }")
  if [ "$status" != "200" ] && [ "$status" != "204" ]; then
    log "ERROR: creating access row returned HTTP ${status}"
    cat /tmp/api.body; exit 1
  fi
  log "Access row created"
else
  log "ERROR: unexpected GET /access status ${status}"
  cat /tmp/api.body; exit 1
fi

# --- 4. Confirm built-in Administrator role exists (sanity check) ---
status=$(api GET "/roles?filter%5Bname%5D%5B_eq%5D=Administrator&limit=1")
if [ "$status" = "200" ]; then
  if grep -q '"name":"Administrator"' /tmp/api.body; then
    log "Built-in Administrator role present (OK — used for admin access)"
  else
    log "WARN: Administrator role lookup returned no results — first-boot bootstrap may still be in progress"
  fi
else
  log "WARN: GET /roles?filter=Administrator returned HTTP ${status}"
fi

# --- 5. Viewer per-collection permission rows ---
#
# These USED to be created here via POST /permissions, but Directus 11.17 has
# a bootstrap-time bug where even a session token with admin_access:true is
# rejected by /permissions (403 FORBIDDEN). Worked around by moving the row
# inserts to a sibling `directus-bootstrap-permissions` compose service that
# runs psql directly against the DB. See directus/bootstrap-permissions.sql.
log "section 5 skipped here — viewer permissions handled by directus-bootstrap-permissions (SQL fallback for #25844-class bug in 11.17)"

# --- 6. Phase 68 MIG-SIGN-02: signage_schedules validation Flow ---
# Filter Flow on items.create + items.update for signage_schedules. Throws a
# JSON-encoded error containing the stable code "schedule_end_before_start"
# when start_hhmm >= end_hhmm. The DB-level CHECK constraint
# ck_signage_schedules_start_before_end (Alembic v1_23_signage_schedule_check)
# is the source of truth; this Flow is the friendly-error layer between
# Directus clients and the raw 23514 Postgres error, so the frontend can
# map the code to an i18n key (Plan 68-05).
#
# Fixed UUIDs (idempotent re-runs, mirrors snapshot YAML documentation block):
SCHEDULE_VALIDATE_FLOW_ID="68aaaaaa-0000-4000-8000-000000000001"
SCHEDULE_VALIDATE_OP_ID="68aaaaaa-0000-4000-8000-000000000002"

log "section 6: signage_schedules validation Flow"

# 6a. Ensure the Run-Script operation exists.
status=$(api GET "/operations/${SCHEDULE_VALIDATE_OP_ID}")
if [ "$status" = "200" ]; then
  log "schedule-validate operation exists (${SCHEDULE_VALIDATE_OP_ID}) — skipping"
elif [ "$status" = "403" ] || [ "$status" = "404" ]; then
  log "creating schedule-validate operation (${SCHEDULE_VALIDATE_OP_ID})"
  # Heredoc-escape backticks and \\n via base64 to dodge JSON-in-JSON quoting.
  SCHEDULE_VALIDATE_CODE='module.exports = async function ({ $trigger }) {\n  const payload = ($trigger && $trigger.payload) || {};\n  let start = payload.start_hhmm;\n  let end = payload.end_hhmm;\n  if ((typeof start !== "number" || typeof end !== "number") && Array.isArray($trigger.keys) && $trigger.keys.length) {\n    return;\n  }\n  if (typeof start === "number" && typeof end === "number" && start >= end) {\n    throw new Error(JSON.stringify({ code: "schedule_end_before_start" }));\n  }\n};'
  status=$(api POST "/operations" "{
    \"id\":\"${SCHEDULE_VALIDATE_OP_ID}\",
    \"flow\":\"${SCHEDULE_VALIDATE_FLOW_ID}\",
    \"name\":\"throw schedule_end_before_start\",
    \"key\":\"validate_start_before_end\",
    \"type\":\"exec\",
    \"position_x\":19,
    \"position_y\":17,
    \"options\":{\"code\":\"${SCHEDULE_VALIDATE_CODE}\"}
  }")
  if [ "$status" != "200" ] && [ "$status" != "204" ]; then
    log "WARN: creating schedule-validate operation returned HTTP ${status}; skipping section 6 (Flow is a friendly-error layer; DB CHECK is source of truth)"
    cat /tmp/api.body
    log "Bootstrap complete (section 6 skipped)."
    exit 0
  fi
  log "schedule-validate operation created"
else
  log "WARN: unexpected GET /operations status ${status}; skipping section 6"
  cat /tmp/api.body
  log "Bootstrap complete (section 6 skipped)."
  exit 0
fi

# 6b. Ensure the Flow exists.
# Trigger options: filter type, scope items.create + items.update,
# collections [signage_schedules]. The operation field links to the op above.
status=$(api GET "/flows/${SCHEDULE_VALIDATE_FLOW_ID}")
if [ "$status" = "200" ]; then
  log "schedule-validate flow exists (${SCHEDULE_VALIDATE_FLOW_ID}) — skipping"
elif [ "$status" = "403" ] || [ "$status" = "404" ]; then
  log "creating schedule-validate flow (${SCHEDULE_VALIDATE_FLOW_ID})"
  status=$(api POST "/flows" "{
    \"id\":\"${SCHEDULE_VALIDATE_FLOW_ID}\",
    \"name\":\"signage_schedules validate start<end\",
    \"icon\":\"fact_check\",
    \"color\":\"#E35169\",
    \"description\":\"Reject signage_schedules writes where start_hhmm >= end_hhmm with stable code 'schedule_end_before_start' before the Postgres CHECK fires.\",
    \"status\":\"active\",
    \"trigger\":\"event\",
    \"accountability\":\"all\",
    \"options\":{
      \"type\":\"filter\",
      \"scope\":[\"items.create\",\"items.update\"],
      \"collections\":[\"signage_schedules\"]
    },
    \"operation\":\"${SCHEDULE_VALIDATE_OP_ID}\"
  }")
  if [ "$status" != "200" ] && [ "$status" != "204" ]; then
    log "ERROR: creating schedule-validate flow returned HTTP ${status}"
    cat /tmp/api.body; exit 1
  fi
  log "schedule-validate flow created"
else
  log "ERROR: unexpected GET /flows status ${status}"
  cat /tmp/api.body; exit 1
fi

log "section 6 complete: signage_schedules Flow active — items.create / items.update guarded by schedule_end_before_start"

log "Bootstrap complete."
