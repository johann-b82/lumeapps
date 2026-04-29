# KPI Light — Setup

This guide takes a clean machine to a running KPI Light stack. Follow sections top-to-bottom. Assumes Docker Engine + Docker Compose v2 are already installed.

---

## Prerequisites

Install and verify the following on the host:

- **Docker Engine + Compose v2** — check with:
  ```bash
  docker compose version
  ```
  The output must start with `Docker Compose version v2.x`. The legacy `docker-compose` (v1, hyphenated) CLI is end-of-life and is NOT supported.
- **openssl** — ships by default on macOS and Linux. Used to generate Directus secrets.
- **git** — to clone the repository.

### Critical warning — decide these BEFORE first bring-up

Directus seeds the first admin user **only against an empty database**. That means:

- `DIRECTUS_ADMIN_EMAIL`
- `DIRECTUS_ADMIN_PASSWORD`

must be chosen BEFORE you run `docker compose up -d` for the first time. Changing either value in `.env` after first boot does NOT change the existing admin user — Directus ignores both variables on every subsequent start. To change them later you must either edit the user via the Directus admin UI, or destroy the Postgres volume (which deletes all data). Put the password in a password manager now.

---

## Bring-up

Step by step. Every command is copy-paste-ready against a clean clone.

1. **Clone the repo and enter it:**
   ```bash
   git clone <repo-url> acm-kpi-light
   cd acm-kpi-light
   ```

2. **Create your environment file:**
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env` and populate each required variable.** Generate secrets verbatim with:
   ```bash
   # DIRECTUS_KEY — random 32-byte base64
   openssl rand -base64 32
   # DIRECTUS_SECRET — random 32-byte base64 (regenerate, don't reuse DIRECTUS_KEY)
   openssl rand -base64 32
   # DIRECTUS_ADMIN_PASSWORD — random 24-byte base64 (store in a password manager)
   openssl rand -base64 24
   ```
   Also set:
   - `DIRECTUS_ADMIN_EMAIL` — any email you and your team will recognise as the bootstrap admin.
   - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — see the defaults and comments in `.env.example`.

   Leave `DIRECTUS_ADMINISTRATOR_ROLE_UUID` at its placeholder value for now — you'll fill it in after step 5.

4. **Create the backups directory** (bind-mounted by the backup sidecar; gitignored):
   ```bash
   mkdir -p backups
   ```

5. **First partial bring-up — database + Directus only.** The Administrator role UUID does not exist until Directus has booted once:
   ```bash
   docker compose up -d db directus
   ```
   Wait for both to report healthy:
   ```bash
   docker compose ps
   ```
   `db` should show `healthy`; `directus` should show `healthy` (takes ~30 seconds on first boot while it initialises its own schema).

6. **Fetch the Administrator role UUID** (copy verbatim — this is the recipe embedded as a comment in `.env.example`):
   ```bash
   TOKEN=$(curl -sf -X POST http://localhost:8055/auth/login \
     -H "Content-Type: application/json" \
     -d "{\"email\":\"$DIRECTUS_ADMIN_EMAIL\",\"password\":\"$DIRECTUS_ADMIN_PASSWORD\"}" \
     | jq -r '.data.access_token')
   curl -sf "http://localhost:8055/roles" \
     -H "Authorization: Bearer $TOKEN" \
     | jq -r '.data[] | select(.name=="Administrator") | .id'
   ```
   Paste the resulting UUID into `.env` as:
   ```
   DIRECTUS_ADMINISTRATOR_ROLE_UUID=<uuid-from-above>
   ```

7. **Full bring-up — all services:**
   ```bash
   docker compose up -d
   ```
   This starts `migrate`, `api`, `frontend`, `backup`, and the `directus-bootstrap-roles` one-shot (which creates the custom `Admin` and `Viewer` roles idempotently).

8. **Verify everything is healthy:**
   ```bash
   docker compose ps
   ```
   Expected: `db`, `api`, `directus`, `backup` show `healthy` or `running`; `migrate` and `directus-bootstrap-roles` show `exited (0)` (they are one-shot services); `frontend` shows `running`.

9. **Sign in.** Open `http://localhost:8055` in a browser and sign in with `DIRECTUS_ADMIN_EMAIL` / `DIRECTUS_ADMIN_PASSWORD`.

---

## First Admin (verify bootstrap)

- Log in to the Directus admin UI at `http://localhost:8055` (direct loopback) or `http://localhost/directus/admin` (via the Caddy proxy, v1.21+). You should land on the **Content** module. Confirm the user-menu avatar in the bottom-left shows the email you set in `.env`.
- Log in to the app at `http://localhost/` (primary entry via Caddy, v1.21+). The direct `http://localhost:5173` Vite dev URL also works for developer workflows. The dashboard should load with the same credentials.

### About the reverse proxy (Phase 64, v1.21+)

Phase 64 added a Caddy reverse proxy fronting the whole stack on port 80. The application entry point is now `http://<host>/`. Caddy routes `/` and `/player/*` to the frontend, `/api/*` to FastAPI, and `/directus/*` to Directus (prefix stripped before forwarding). Because the SPA reaches Directus same-origin via `/directus`, the old `CORS_ENABLED` / `CORS_ORIGIN` / `CORS_CREDENTIALS` env vars are no longer needed and were removed from `docker-compose.yml`. The existing direct-port exposures (`:5173`, `:8000`, `:8055`) stay open for developer access; normal operator workflows should use `:80`.

If either sign-in fails, see **Troubleshooting** below.

---

## Promote Viewer to Admin

This is the click-path for granting an existing Viewer full admin rights via the Directus UI. All steps are text-only.

1. Sign in to the Directus admin UI at `http://localhost:8055` as an Administrator.
2. In the left sidebar, click **User Directory**.
3. Click the row of the user you want to promote. The user-detail form opens.
4. Locate the **Role** field (typically on the right side of the form, or in the main body depending on layout).
5. Change the role from **Viewer** to **Administrator**.
6. Click **Save** (checkmark icon, top-right of the page).
7. The new role takes effect on the user's next JWT refresh — i.e., within their current token TTL. To force immediate effect, have the user sign out and sign back in.

---

## Backups

The stack includes a backup sidecar service (named `backup` in `docker-compose.yml`).

- **Schedule:** nightly at **02:00 Europe/Berlin** (the sidecar sets `TZ: Europe/Berlin` so cron fires on operator-local time, not UTC). If your host is in another timezone, edit the `TZ:` value under the `backup` service in `docker-compose.yml` and run `docker compose up -d backup` to recreate the container.
- **Output directory:** `./backups/` on the host (bind-mounted into the sidecar, gitignored).
- **Filename pattern:** `kpi-YYYY-MM-DD.sql.gz` — plain-format `pg_dump` piped through `gzip`. A second run on the same day overwrites that day's file.
- **Retention:** 14 days. Files older than 14 days are automatically deleted after each dump.
- **Manual trigger** (for testing or an ad-hoc dump before a risky change):
  ```bash
  docker compose exec backup /usr/local/bin/dump.sh
  ```
- **Verify the sidecar is alive:**
  ```bash
  docker compose ps backup
  docker compose logs backup --tail 20
  ```
  You should see `crontab installed; starting crond (TZ=Europe/Berlin)` in the logs.

---

## Restore

Use `./scripts/restore.sh` to restore a dump produced by the backup sidecar. Positional argument only, no flags:

```bash
./scripts/restore.sh backups/kpi-2026-04-15.sql.gz
```

- The script accepts both `.sql` (plain) and `.sql.gz` (gzipped) files transparently.
- It streams the dump into the running `db` container via `psql` with `ON_ERROR_STOP=1`, so the first error aborts the restore instead of silently continuing.
- **Warning:** the restore replaces all data in `$POSTGRES_DB` — the dump is produced with `pg_dump --clean --if-exists`, so every object is dropped and recreated. A 5-second countdown before streaming begins gives you a chance to Ctrl-C out.
- The stack must be up (`docker compose up -d`) before running restore — the script uses `docker compose exec -T db psql ...` inside the existing `db` container.

This exact restore path was exercised end-to-end during Phase 30 execution; the cycle (dump → restore → tables verified) is recorded in `.planning/phases/30-bring-up-docs-backup/30-01-SUMMARY.md`.

---

## Troubleshooting

**"I changed `DIRECTUS_ADMIN_EMAIL` / `DIRECTUS_ADMIN_PASSWORD` in `.env` but sign-in still uses the old values."**
By design. Directus seeds the first admin only against an empty database; both variables are ignored on subsequent boots. Fix: sign in as the existing admin via `http://localhost:8055`, open **User Directory**, and edit the user directly. The only alternative is destroying the Postgres volume (see next entry — it deletes everything).

**"I ran `docker compose down -v` and the database is gone."**
`-v` deletes named volumes, including `postgres_data`. Everything Directus and the app stored is gone. Use `docker compose down` (without `-v`) to stop services while preserving data. To recover: bring the stack back up (`docker compose up -d`) and restore from the most recent dump in `./backups/` via `./scripts/restore.sh backups/kpi-<date>.sql.gz`.

**"The `backup` container logs a permission error when writing to `/backups`."**
The host's `./backups/` directory and the sidecar's UID don't agree. Quick fix:
```bash
chmod 777 backups
```
Longer-term fix: add `user: "${UID}:${GID}"` to the `backup` service in `docker-compose.yml` so the sidecar writes as the host user.

**"Backup timestamps are 2 hours off from what I expect."**
The sidecar defaults to `TZ: Europe/Berlin`. Edit the `TZ:` value under the `backup` service in `docker-compose.yml` to your local zone (e.g. `TZ: America/New_York`) and run:
```bash
docker compose up -d backup
```
to recreate the container with the new timezone.

**"`docker compose up` hangs on the Directus healthcheck."**
Confirm `DIRECTUS_KEY`, `DIRECTUS_SECRET`, `DIRECTUS_ADMIN_EMAIL`, and `DIRECTUS_ADMIN_PASSWORD` are all set and non-empty in `.env`. Directus refuses to boot without `KEY` and `SECRET`; missing admin credentials leave it in a half-initialised state. Regenerate the secrets with the `openssl rand` commands above if unsure.

**"`./scripts/restore.sh` fails with `no such container: db` or similar."**
The restore script requires the stack to be running so it can `docker compose exec -T db psql ...`. Run `docker compose up -d` first, wait for `db` to report healthy via `docker compose ps`, then retry the restore.

**"`curl ... /auth/login` returns 401 when fetching the Administrator role UUID."**
Your `DIRECTUS_ADMIN_EMAIL` and `DIRECTUS_ADMIN_PASSWORD` don't match what Directus seeded on first boot. Either sign in at `http://localhost:8055` with the values you actually set and use those, or destroy the volume (`docker compose down -v`; this deletes all data) and start over from step 1 with fresh values.
