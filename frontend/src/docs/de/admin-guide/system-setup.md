# Systemeinrichtung

Diese Anleitung fuehrt Sie durch die Inbetriebnahme des KPI Dashboards -- von einem frischen Repository-Klon bis zur laufenden Anwendung. Sie konfigurieren Umgebungsvariablen, starten den Docker-Compose-Stack und ueberpruefen, ob alle Dienste fehlerfrei laufen.

## Voraussetzungen

Folgendes muss auf Ihrem Rechner installiert sein:

- **Docker** (mit dem Compose-v2-Plugin -- verwenden Sie `docker compose`, nicht das veraltete `docker-compose`)
- **Git** zum Klonen des Repositories

Das ist alles. Saemtliche Laufzeitabhaengigkeiten (PostgreSQL, FastAPI, React, Directus) laufen in Containern.

## Umgebungskonfiguration

1. Kopieren Sie die Beispiel-Umgebungsdatei:

```bash
cp .env.example .env
```

2. Oeffnen Sie `.env` in Ihrem Editor und tragen Sie die erforderlichen Werte ein:

| Variable | Zweck |
|----------|-------|
| `POSTGRES_USER` | PostgreSQL-Benutzername fuer die KPI-Datenbank |
| `POSTGRES_PASSWORD` | PostgreSQL-Passwort |
| `POSTGRES_DB` | Datenbankname (z.B. `kpi_db`) |
| `DEX_KPI_SECRET` | OIDC-Client-Secret, geteilt zwischen Dex und der API |
| `DEX_OUTLINE_SECRET` | OIDC-Client-Secret, geteilt zwischen Dex und Outline |
| `SESSION_SECRET` | Signaturschluessel fuer API-Session-Cookies |
| `OUTLINE_SECRET_KEY` | Outline-Anwendungsschluessel |
| `OUTLINE_UTILS_SECRET` | Outline-Hilfsschluessel |
| `OUTLINE_DB_PASSWORD` | Passwort fuer die dedizierte Outline-Datenbank |

> **Tipp:** Generieren Sie Secrets mit `openssl rand -hex 32`. Jedes Secret sollte einzigartig sein -- verwenden Sie nicht denselben Wert fuer mehrere Variablen.

> **Hinweis:** Committen Sie Ihre `.env`-Datei niemals in die Versionskontrolle. Das Repository liefert `.env.example` nur mit Platzhalterwerten aus. Die echte `.env` ist in `.gitignore` eingetragen.

## Anwendung starten

1. Starten Sie alle Dienste im Hintergrund:

```bash
docker compose up -d
```

2. Warten Sie, bis die Startsequenz abgeschlossen ist. Die Dienste starten in dieser Reihenfolge:
   - **db** -- PostgreSQL startet und besteht den Health-Check (`pg_isready`)
   - **migrate** -- Alembic fuehrt alle ausstehenden Migrationen aus und beendet sich
   - **api** und **directus** -- starten, sobald die Datenbank bereit ist
   - **frontend** -- startet, sobald die API fehlerfrei laeuft
   - **npm** -- Nginx Proxy Manager startet zuletzt, sobald alle Upstream-Dienste fehlerfrei sind

3. Ueberpruefen Sie, ob alle Dienste laufen:

```bash
docker compose ps
```

4. Zugriff auf die Anwendung:
   - **Anwendung (ueber Caddy-Reverse-Proxy):** `http://<host>/` -- das ist der primaere Einstieg fuer alle im LAN.
   - **Frontend (direkter Vite-Dev-Zugriff):** `http://localhost:5173`
   - **Directus-Admin-UI:** `http://localhost:8055` (direkt) oder `http://<host>/directus/admin` (ueber den Proxy)
   - **NPM-Admin-UI:** `http://localhost:81`

> **Hinweis zum Reverse-Proxy:** Das KPI Dashboard erreichst du unter `http://<host>/` -- ein Caddy-Reverse-Proxy liegt davor. Directus laeuft auf demselben Host unter `/directus/*`. Die Ports `:5173`, `:8000` und `:8055` bleiben fuer die Entwicklung direkt erreichbar. Im normalen Betrieb nutze `:80`.

## Administrator-Rollen-UUID abrufen

Nach dem ersten Start erstellt Directus Standardrollen. Sie muessen die UUID der Administrator-Rolle ermitteln und in Ihrer Umgebung setzen:

1. Oeffnen Sie die Directus-Admin-UI unter `http://localhost:8055` und melden Sie sich mit den Zugangsdaten aus Ihrer `.env`-Datei an.

2. Navigieren Sie zu **Settings > Roles & Permissions** und klicken Sie auf die **Administrator**-Rolle. Die UUID wird in der Adressleiste angezeigt.

3. Alternativ koennen Sie die UUID ueber die Directus-API abrufen:

```bash
curl -s http://localhost:8055/roles \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" | jq '.data[] | select(.name == "Administrator") | .id'
```

4. Setzen Sie die UUID in Ihrer `.env`-Datei:

```
DIRECTUS_ADMINISTRATOR_ROLE_UUID=your-uuid-here
```

5. Starten Sie den Stack neu, um die Aenderung zu uebernehmen:

```bash
docker compose down && docker compose up -d
```

## Verwandte Artikel

- [Architektur](/docs/admin-guide/architecture) -- verstehen Sie, wie die Dienste zusammenhaengen
- [Benutzerverwaltung](/docs/admin-guide/user-management) -- Rollen und Berechtigungen einrichten
