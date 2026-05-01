# System Setup

This guide walks you through bringing up the KPI Dashboard from a fresh clone to a running application. You will configure environment variables, start the Docker Compose stack, and verify that every service is healthy.

## Prerequisites

You need the following installed on your machine:

- **Docker** (with the Compose v2 plugin -- use `docker compose`, not the legacy `docker-compose`)
- **Git** to clone the repository

That is all. Every runtime dependency (PostgreSQL, FastAPI, React, Directus) runs inside containers.

## Environment Configuration

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Open `.env` in your editor and fill in the required values:

| Variable | Purpose |
|----------|---------|
| `POSTGRES_USER` | PostgreSQL username for the KPI database |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | Database name (e.g. `kpi_db`) |
| `DEX_KPI_SECRET` | OIDC client secret shared between Dex and the API |
| `DEX_OUTLINE_SECRET` | OIDC client secret shared between Dex and Outline |
| `SESSION_SECRET` | Signing key for API session cookies |
| `OUTLINE_SECRET_KEY` | Outline application secret |
| `OUTLINE_UTILS_SECRET` | Outline utilities secret |
| `OUTLINE_DB_PASSWORD` | Password for the dedicated Outline database |

> **Tip:** Generate secrets with `openssl rand -hex 32`. Each secret should be unique -- do not reuse the same value across variables.

> **Note:** Never commit your `.env` file to version control. The repository ships `.env.example` with placeholder values only. The real `.env` is listed in `.gitignore`.

## Starting the Application

1. Start all services in detached mode:

```bash
docker compose up -d
```

2. Wait for the startup sequence to complete. Services come up in this order:
   - **db** -- PostgreSQL starts and passes its health check (`pg_isready`)
   - **migrate** -- Alembic runs all pending migrations, then exits
   - **api** and **directus** -- start once the database is ready
   - **frontend** -- starts once the API is healthy
   - **npm** -- Nginx Proxy Manager starts last, once all upstream services are healthy

3. Verify that all services are running:

```bash
docker compose ps
```

4. Access the application:
   - **App (via Caddy reverse proxy):** `http://<host>/` -- this is the primary entry point for everyone on the LAN.
   - **Frontend (direct Vite dev):** `http://localhost:5173`
   - **Directus admin UI:** `http://localhost:8055` (direct) or `http://<host>/directus/admin` (via the proxy)
   - **NPM admin UI:** `http://localhost:81`

> **Reverse proxy note:** The KPI Dashboard is served at `http://<host>/` through a Caddy reverse proxy. Directus is reachable on the same host at `/directus/*`. The direct ports `:5173`, `:8000`, and `:8055` stay open for development. Normal operator workflows should use `:80`.

## Fetching the Administrator Role UUID

After the first boot, Directus creates default roles. You need to retrieve the Administrator role UUID and set it in your environment:

1. Open the Directus admin UI at `http://localhost:8055` and log in with the credentials from your `.env` file.

2. Navigate to **Settings > Roles & Permissions** and click on the **Administrator** role. The UUID is shown in the URL bar.

3. Alternatively, fetch it via the Directus API:

```bash
curl -s http://localhost:8055/roles \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" | jq '.data[] | select(.name == "Administrator") | .id'
```

4. Set the UUID in your `.env` file:

```
DIRECTUS_ADMINISTRATOR_ROLE_UUID=your-uuid-here
```

5. Restart the stack to apply the change:

```bash
docker compose down && docker compose up -d
```

## Related Articles

- [Architecture](/docs/admin-guide/architecture) -- understand how the services connect
- [User Management](/docs/admin-guide/user-management) -- set up roles and permissions
