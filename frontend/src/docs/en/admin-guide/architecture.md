# Architecture

This article describes how the KPI Dashboard services fit together, how they start, and how data flows through the system.

## Services

The application is composed of the following Docker Compose services:

| Service | Technology | Port | Role |
|---------|-----------|------|------|
| **db** | PostgreSQL 17 (`postgres:17-alpine`) | 5432 (internal) | Primary database for KPI data, upload history, and app settings |
| **migrate** | Alembic (one-shot) | -- | Runs pending database migrations on startup, then exits |
| **api** | FastAPI + SQLAlchemy 2.0 + asyncpg | 8000 | REST API for file uploads, KPI queries, settings, and Personio sync |
| **frontend** | React 19 + Vite 8 + TanStack Query + Recharts 3 | 5173 | Single-page application serving the dashboard UI and documentation |
| **directus** | Directus 11 | 8055 (localhost only) | Identity and authentication layer; manages user accounts and roles |
| **directus-bootstrap-roles** | curl (sidecar) | -- | Idempotent one-shot container that creates default Directus roles on first boot |
| **dex** | Dex OIDC (`ghcr.io/dexidp/dex:v2.43.0`) | 5556 (internal) | OpenID Connect provider bridging Directus to the API and Outline |
| **npm** | Nginx Proxy Manager 2.11 | 80, 443, 81 | Reverse proxy and TLS termination for all public-facing services |
| **outline** | Outline Wiki 0.86 | 3000 (internal) | Team knowledge base, authenticated via Dex OIDC |
| **outline-db** | PostgreSQL 17 (`postgres:17-alpine`) | 5432 (internal) | Dedicated database for Outline |
| **outline-redis** | Redis 7 (`redis:7-alpine`) | 6379 (internal) | Cache and session store for Outline |
| **backup** | pg_dump (scheduled) | -- | Periodic PostgreSQL backup service |

## Startup Sequence

Services declare explicit health checks and `depends_on` conditions (`service_healthy` or `service_completed_successfully`) to enforce a safe startup order:

1. **db** starts and becomes healthy (`pg_isready` passes)
2. **migrate** runs `alembic upgrade head`, then exits successfully
3. **api** starts (depends on migrate completing) and exposes `/health`
4. **directus** starts (depends on db being healthy)
5. **frontend** starts (depends on api being healthy)
6. **dex** starts independently (uses SQLite, no external DB dependency)
7. **npm** starts last (depends on api, frontend, dex, and outline all being healthy)

This chain ensures no service receives traffic before its dependencies are ready. The `condition: service_healthy` pattern prevents the startup-crash race condition that plain `depends_on` allows.

## Data Flow

The primary data flows through the system are:

**Dashboard flow:** Browser loads the Vite SPA on port 5173 (or via NPM on 443). The React app uses TanStack Query to fetch KPI data from the FastAPI API on port 8000. The API queries PostgreSQL on port 5432 and returns JSON responses.

**File upload flow:** The user drops a CSV/TXT file in the upload UI. The frontend sends a multipart POST to `/api/upload`. FastAPI parses the file with pandas, validates against the fixed schema, and bulk-inserts rows into PostgreSQL. The response includes the row count and any validation errors.

**Authentication flow:** The browser redirects to Dex (via NPM at `https://auth.internal/dex/auth`) for OIDC login. Dex authenticates against its connector (Directus), issues tokens, and redirects back. The API validates the token and creates a session cookie.

**HR sync flow:** The API calls the external Personio API to fetch employee data, transforms it, and stores it in PostgreSQL. This runs on a configurable schedule or on-demand from the UI.

**Directus data isolation:** The tables `upload_batches`, `sales_records`, `app_settings`, and Personio-related tables are excluded from the Directus Data Model UI via `DB_EXCLUDE_TABLES`. Directus only manages its own identity tables.

## Tech Stack Summary

| Layer | Technologies |
|-------|-------------|
| Backend | FastAPI + SQLAlchemy 2.0 + asyncpg |
| Database | PostgreSQL 17 |
| Frontend | React 19 + Vite 8 + TanStack Query + Recharts 3 |
| Identity | Directus 11 + Dex OIDC |
| Proxy | Nginx Proxy Manager 2.11 |
| Wiki | Outline 0.86 |

## Related Articles

- [System Setup](/docs/admin-guide/system-setup) -- deploy the stack step by step
- [Personio Integration](/docs/admin-guide/personio) -- configure the HR data sync
