# API Route Contract — Admin vs Viewer

**Milestone:** v1.11-directus
**Last updated:** 2026-04-15 (Phase 28)
**Enforcement:** FastAPI dependency `app.security.directus_auth.require_admin` on every mutation route. See `backend/tests/test_rbac.py` for the machine-verified matrix.

## Roles

- **Admin** — full read + write access across all `/api/*` routes.
- **Viewer** — read access only. Mutation attempts return HTTP 403 with body:
  ```json
  {"detail": "admin role required"}
  ```
- **Public** — unauthenticated endpoints (no JWT required): `/health`, `/docs`, `/openapi.json`.

Role is resolved from the Directus-issued JWT (HS256, shared secret). Role changes made in the Directus admin UI take effect on the user's next JWT refresh — no server-side session invalidation needed (stateless JWT).

## Route Matrix

| Method | Path                            | Viewer | Admin | Notes |
|--------|---------------------------------|:------:|:-----:|-------|
| GET    | /api/kpis                       |   ✓    |   ✓   | Sales KPI summary |
| GET    | /api/kpis/chart                 |   ✓    |   ✓   | Chart data |
| GET    | /api/kpis/latest-upload         |   ✓    |   ✓   | Most recent upload metadata |
| GET    | /api/hr/kpis                    |   ✓    |   ✓   | HR KPI summary |
| GET    | /api/hr/kpis/history            |   ✓    |   ✓   | HR KPI time series |
| GET    | /api/data/sales                 |   ✓    |   ✓   | Sales record listing |
| GET    | /api/data/employees             |   ✓    |   ✓   | Employee record listing |
| GET    | /api/settings                   |   ✓    |   ✓   | Read settings (colors, app name) |
| GET    | /api/settings/personio-options  |   ✓    |   ✓   | Live Personio metadata — read-only |
| GET    | /api/settings/logo              |   ✓    |   ✓   | Serves raw logo bytes |
| GET    | /api/uploads                    |   ✓    |   ✓   | Upload history |
| GET    | /api/sync/meta                  |   ✓    |   ✓   | Last sync metadata |
| POST   | /api/upload                     |   —    |   ✓   | ERP file upload |
| DELETE | /api/uploads/{batch_id}         |   —    |   ✓   | Cascade-deletes sales records |
| POST   | /api/sync                       |   —    |   ✓   | Full Personio sync |
| POST   | /api/sync/test                  |   —    |   ✓   | Personio credential test |
| PUT    | /api/settings                   |   —    |   ✓   | Update colors / app name / credentials |
| POST   | /api/settings/logo              |   —    |   ✓   | Logo upload |
| GET    | /health                         | public | public | No auth required |
| GET    | /docs                           | public | public | OpenAPI UI (no auth) |
| GET    | /openapi.json                   | public | public | OpenAPI schema (no auth) |

## Error Shapes

| HTTP | Condition | Body |
|------|-----------|------|
| 401  | Missing or invalid JWT | `{"detail": "invalid or missing authentication token"}` |
| 403  | Valid JWT, Viewer role on a mutation route | `{"detail": "admin role required"}` |

## Verification

- Automated: `cd backend && python -m pytest tests/test_rbac.py -v`
- Source of truth: `backend/app/security/directus_auth.py::require_admin` (the dependency) + decorators in `backend/app/routers/{uploads,sync,settings}.py`
