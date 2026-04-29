-- bootstrap-permissions.sql — Viewer permission rows for Directus collections.
--
-- Why SQL instead of REST:
--   In Directus 11.17 the bootstrap admin user reliably has admin_access:true
--   in its JWT and a directus_access row to the Administrator policy, yet
--   POST/GET /permissions still returns 403 FORBIDDEN. Reproduces on a fresh
--   cold-boot DB and is independent of session vs. static token.
--
-- This file is run by the `directus-bootstrap-permissions` compose service
-- (postgres:17-alpine image) AFTER `directus-bootstrap-roles` has provisioned
-- the Viewer Read policy + role + role-policy access link via REST.
--
-- Idempotency:
--   - directus_permissions.id is an integer auto-increment column (no UUID),
--     so we cannot use ON CONFLICT(id). Instead, delete all permission rows
--     for the Viewer Read policy first, then re-insert. Safe because Viewer
--     permissions are owned exclusively by this script.

\set ON_ERROR_STOP on

-- Match bootstrap-roles.sh VIEWER_POLICY_ID.
\set viewer_policy_id 'a2222222-aaaa-aaaa-aaaa-aaaaaaaaaaaa'

DELETE FROM directus_permissions WHERE policy = :'viewer_policy_id';

-- AUTHZ-01: sales_records — mirrors SalesRecordRead (10 column-backed fields).
INSERT INTO directus_permissions (policy, collection, action, fields, permissions)
VALUES (
  :'viewer_policy_id',
  'sales_records',
  'read',
  'id,order_number,customer_name,city,order_date,total_value,remaining_value,responsible_person,project_name,status_code',
  '{}'
);

-- AUTHZ-01: personio_employees — mirrors EmployeeRead, COLUMN-BACKED ONLY.
-- Compute-derived fields (total_hours, overtime_hours, overtime_ratio) come
-- from FastAPI /api/data/employees/overtime; intentionally excluded here.
INSERT INTO directus_permissions (policy, collection, action, fields, permissions)
VALUES (
  :'viewer_policy_id',
  'personio_employees',
  'read',
  'id,first_name,last_name,status,department,position,hire_date,termination_date,weekly_working_hours',
  '{}'
);

-- AUTHZ-03: directus_users — explicit allowlist (id, email, first_name,
-- last_name, role, avatar). Sensitive columns (2FA secret, auth data,
-- external identifier, token) are excluded.
INSERT INTO directus_permissions (policy, collection, action, fields, permissions)
VALUES (
  :'viewer_policy_id',
  'directus_users',
  'read',
  'id,email,first_name,last_name,role,avatar',
  '{}'
);

-- v1.23 C-1: upload_batches — mirrors UploadBatchSummary. Read for both
-- Admin (via admin_access:true) and Viewer (via this row).
INSERT INTO directus_permissions (policy, collection, action, fields, permissions)
VALUES (
  :'viewer_policy_id',
  'upload_batches',
  'read',
  'id,filename,uploaded_at,row_count,error_count,status',
  '{}'
);

-- Phase 66 MIG-AUTH-01: directus_roles — Viewer needs role.name for the FE
-- readMe({ fields: ['id','email','role.name'] }) call to resolve.
INSERT INTO directus_permissions (policy, collection, action, fields, permissions)
VALUES (
  :'viewer_policy_id',
  'directus_roles',
  'read',
  'id,name',
  '{}'
);

-- AUTHZ-02 / v1.23 C-2..C-4: intentionally NO permission rows on signage_*
-- collections for Viewer. Admin reads via admin_access:true on the
-- Administrator policy; explicit deny for Viewer is the absence of a row.

-- Report what we did so the operator can see in `docker compose logs`.
SELECT 'bootstrap-permissions: ' || count(*) || ' viewer rows inserted' AS status
FROM directus_permissions
WHERE policy = :'viewer_policy_id';
