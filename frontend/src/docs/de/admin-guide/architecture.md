# Architektur

Dieser Artikel beschreibt, wie die Dienste des KPI Dashboards zusammenarbeiten, in welcher Reihenfolge sie starten und wie Daten durch das System fliessen.

## Dienste

Die Anwendung besteht aus den folgenden Docker-Compose-Diensten:

| Dienst | Technologie | Port | Aufgabe |
|--------|------------|------|---------|
| **db** | PostgreSQL 17 (`postgres:17-alpine`) | 5432 (intern) | Primaerdatenbank fuer KPI-Daten, Upload-Verlauf und App-Einstellungen |
| **migrate** | Alembic (einmalig) | -- | Fuehrt ausstehende Datenbankmigrationen beim Start aus und beendet sich |
| **api** | FastAPI + SQLAlchemy 2.0 + asyncpg | 8000 | REST-API fuer Datei-Uploads, KPI-Abfragen, Einstellungen und Personio-Sync |
| **frontend** | React 19 + Vite 8 + TanStack Query + Recharts 3 | 5173 | Single-Page-Anwendung mit Dashboard-UI und Dokumentation |
| **directus** | Directus 11 | 8055 (nur localhost) | Identitaets- und Authentifizierungsschicht; verwaltet Benutzerkonten und Rollen |
| **directus-bootstrap-roles** | curl (Sidecar) | -- | Idempotenter Einmal-Container, der beim ersten Start Standardrollen in Directus anlegt |
| **dex** | Dex OIDC (`ghcr.io/dexidp/dex:v2.43.0`) | 5556 (intern) | OpenID-Connect-Provider, der Directus mit der API und Outline verbindet |
| **npm** | Nginx Proxy Manager 2.11 | 80, 443, 81 | Reverse-Proxy und TLS-Terminierung fuer alle oeffentlich erreichbaren Dienste |
| **outline** | Outline Wiki 0.86 | 3000 (intern) | Team-Wissensdatenbank, authentifiziert ueber Dex OIDC |
| **outline-db** | PostgreSQL 17 (`postgres:17-alpine`) | 5432 (intern) | Dedizierte Datenbank fuer Outline |
| **outline-redis** | Redis 7 (`redis:7-alpine`) | 6379 (intern) | Cache und Session-Speicher fuer Outline |
| **backup** | pg_dump (geplant) | -- | Periodischer PostgreSQL-Sicherungsdienst |

## Startsequenz

Die Dienste deklarieren explizite Health-Checks und `depends_on`-Bedingungen (`service_healthy` bzw. `service_completed_successfully`), um eine sichere Startreihenfolge zu gewaehrleisten:

1. **db** startet und wird als fehlerfrei gemeldet (`pg_isready` ist erfolgreich)
2. **migrate** fuehrt `alembic upgrade head` aus und beendet sich erfolgreich
3. **api** startet (abhaengig vom erfolgreichen Abschluss von migrate) und stellt `/health` bereit
4. **directus** startet (abhaengig davon, dass db fehlerfrei laeuft)
5. **frontend** startet (abhaengig davon, dass api fehlerfrei laeuft)
6. **dex** startet unabhaengig (nutzt SQLite, keine externe DB-Abhaengigkeit)
7. **npm** startet zuletzt (abhaengig davon, dass api, frontend, dex und outline alle fehlerfrei sind)

Diese Kette stellt sicher, dass kein Dienst Anfragen empfaengt, bevor seine Abhaengigkeiten bereit sind. Das `condition: service_healthy`-Muster verhindert die Startup-Crash-Race-Condition, die ein einfaches `depends_on` zulaesst.

## Datenfluss

Die wichtigsten Datenfluesse durch das System:

**Dashboard-Fluss:** Der Browser laedt die Vite-SPA auf Port 5173 (oder ueber NPM auf Port 443). Die React-App nutzt TanStack Query, um KPI-Daten von der FastAPI-API auf Port 8000 abzurufen. Die API fragt PostgreSQL auf Port 5432 ab und liefert JSON-Antworten.

**Datei-Upload-Fluss:** Der Benutzer legt eine CSV-/TXT-Datei in der Upload-UI ab. Das Frontend sendet einen Multipart-POST an `/api/upload`. FastAPI parst die Datei mit pandas, validiert gegen das feste Schema und fuegt die Zeilen per Bulk-Insert in PostgreSQL ein. Die Antwort enthaelt die Zeilenanzahl und eventuelle Validierungsfehler.

**Authentifizierungsfluss:** Der Browser leitet zu Dex weiter (ueber NPM unter `https://auth.internal/dex/auth`) fuer den OIDC-Login. Dex authentifiziert ueber seinen Connector (Directus), stellt Tokens aus und leitet zurueck. Die API validiert das Token und erstellt ein Session-Cookie.

**HR-Sync-Fluss:** Die API ruft die externe Personio-API auf, um Mitarbeiterdaten abzurufen, transformiert sie und speichert sie in PostgreSQL. Dies laeuft nach einem konfigurierbaren Zeitplan oder auf Abruf ueber die UI.

**Directus-Datenisolierung:** Die Tabellen `upload_batches`, `sales_records`, `app_settings` und Personio-bezogene Tabellen sind ueber `DB_EXCLUDE_TABLES` aus der Directus-Data-Model-UI ausgeschlossen. Directus verwaltet nur seine eigenen Identitaetstabellen.

## Tech-Stack-Zusammenfassung

| Schicht | Technologien |
|---------|-------------|
| Backend | FastAPI + SQLAlchemy 2.0 + asyncpg |
| Datenbank | PostgreSQL 17 |
| Frontend | React 19 + Vite 8 + TanStack Query + Recharts 3 |
| Identitaet | Directus 11 + Dex OIDC |
| Proxy | Nginx Proxy Manager 2.11 |
| Wiki | Outline 0.86 |

## Verwandte Artikel

- [Systemeinrichtung](/docs/admin-guide/system-setup) -- den Stack Schritt fuer Schritt bereitstellen
- [Personio-Integration](/docs/admin-guide/personio) -- die HR-Datensynchronisierung konfigurieren
