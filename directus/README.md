# Directus roles — as code

This directory holds the **roles-as-code** bootstrap for the Directus admin instance.

## Why not `snapshot.yml`?

Plan 02 originally committed a `directus/snapshot.yml` using the v10 shape
(top-level `roles:` + `permissions:` lists). Directus 11 refactored access
control into **policies** + **roles** + **access** (see Directus 11 release
notes), and `npx directus schema apply` on a v10-shaped snapshot fails with
obscure errors or silently no-ops on v11. The snapshot was removed and
replaced with a REST-API bootstrap script.

## How it works

`bootstrap-roles.sh` is mounted read-only into a one-shot sidecar
(`directus-bootstrap-roles` in `docker-compose.yml`) that runs after the
main `directus` service is healthy. The script:

1. Logs in as the first Admin (from `DIRECTUS_ADMIN_EMAIL` / `DIRECTUS_ADMIN_PASSWORD`).
2. `GET`s each of the fixed-UUID records below — if absent, `POST`s to create.
3. Exits 0. Re-running is a no-op (every write is gated by a GET).

## Fixed UUIDs

| Record                  | UUID                                   | Purpose                                    |
| ----------------------- | -------------------------------------- | ------------------------------------------ |
| Viewer Read policy      | `a2222222-aaaa-aaaa-aaaa-aaaaaaaaaaaa` | `admin_access:false`, `app_access:true`    |
| Viewer role             | `a2222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb` | Human-assignable role, read-only           |
| Viewer access row       | `a2222222-cccc-cccc-cccc-cccccccccccc` | Links Viewer role → Viewer Read policy     |

## Admin role

There is no custom "Admin" role. Directus 11 ships a built-in
**`Administrator`** role (created by `ADMIN_EMAIL`/`ADMIN_PASSWORD` bootstrap).
Downstream code — including Phase 27's FastAPI `require_role` — must treat
`"Administrator"` as the admin role name (not `"Admin"`). The CONTEXT
document's `Admin` label refers conceptually to this realized role.

## Editing roles

- New role / permission change? Edit `bootstrap-roles.sh` and commit.
- Manual edits in the Directus UI persist (this script is additive, never
  destructive) but **will drift from version control**. Prefer script
  changes + re-run the sidecar: `docker compose up -d directus-bootstrap-roles`.

## Running the sidecar manually

```bash
docker compose up -d directus-bootstrap-roles
docker compose logs directus-bootstrap-roles
```

Logs should end with `Bootstrap complete.` and the container should exit 0.
