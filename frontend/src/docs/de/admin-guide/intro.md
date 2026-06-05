# Administratorhandbuch

Das Administratorhandbuch behandelt alles, was Sie zur Einrichtung, Konfiguration und Wartung des KPI Dashboards wissen muessen. Ob Sie die Anwendung zum ersten Mal bereitstellen oder eine bestehende Installation verwalten -- diese Artikel fuehren Sie durch jeden Aspekt des Systems.

## Systemeinrichtung

Erfahren Sie, wie Sie Umgebungsvariablen konfigurieren, den Docker-Compose-Stack starten und ueberpruefen, ob alle Dienste laufen. Dies ist der richtige Einstieg, wenn Sie das KPI Dashboard zum ersten Mal bereitstellen.

[Zur Systemeinrichtung](/docs/admin-guide/system-setup)

## Architektur

Verstehen Sie, wie die Dienste zusammenarbeiten -- von der PostgreSQL-Datenbank ueber das FastAPI-Backend bis zum React-Frontend, plus Directus fuer die Identitaetsverwaltung. Behandelt die Startsequenz, den Datenfluss und den Tech-Stack.

[Zur Architekturuebersicht](/docs/admin-guide/architecture)

## Digital Signage

Raspberry-Pi-Kiosks bereitstellen, Playlists erstellen und Geräten über Tags zuweisen. Behandelt Medienaufnahme (Drag-and-drop, URL/HTML, PPTX-Konvertierung), Zeitpläne und Offline-Verhalten.

[Zum Digital-Signage-Handbuch](/docs/admin-guide/digital-signage)

## Personio-Integration

Konfigurieren Sie die Verbindung zu Personio fuer die automatische HR-Datensynchronisierung, einschliesslich Zugangsdaten, Sync-Intervallen und Attribut-Zuordnung.

[Zur Personio-Integration](/docs/admin-guide/personio)

## Sensor Monitor

SNMP-Umgebungssensoren (Temperatur + Luftfeuchtigkeit) einrichten, Abfrage-Kadenz und Schwellenwerte setzen, und pro Sensor die Diagrammfarbe konfigurieren.

[Zum Sensor-Monitor-Handbuch](/docs/admin-guide/sensor-monitor)

## Benutzerverwaltung

Verwalten Sie Benutzerrollen und Zugriffsrechte ueber Directus, einschliesslich der Einrichtung von Administrator- und Betrachter-Rollen.

[Zur Benutzerverwaltung](/docs/admin-guide/user-management)

## Eingebettete Apps (v1.46+ / v1.48+)

Drei Drittanbieter-Apps werden mit dem Stack ausgeliefert und starten zusammen mit `docker compose up`:

- **Dokumente — Paperless-ngx** (ab v1.46) — eingebunden unter `/paperless/*`, Postgres-Backend, vollständige Directus-SSO via `X-Remote-User`. Lokale Nutzer werden beim ersten Zugriff automatisch angelegt.
- **PDF-Werkzeuge — Stirling-PDF** (ab v1.48) — eingebunden unter `/pdf/*`, Community Edition mit deaktiviertem internen Login. Die Caddy-`forward_auth` ist die einzige Authentifizierungs-Schranke.
- **Projekte — OpenProject** (ab v1.48) — eingebunden unter `/op/*`, dedizierte `openproject`-Postgres-Datenbank. Das Caddy-Gate hält unauthentifizierte Browser von der OP-Login-Seite fern; die Community Edition unterstützt keine Header-SSO, daher müssen sich Nutzer beim ersten Besuch zusätzlich in OpenProject anmelden. Vor dem ersten Start `OPENPROJECT_ADMIN_PASSWORD` in `.env` setzen.

Alle drei werden mit `docker compose down` zusammen gestoppt. Soll eine App auf einem Host übersprungen werden, beim Start auf null skalieren: `docker compose up -d --scale stirling=0`.

## Einstellungen-Layout

Der Einstellungsbereich ist in drei Seiten aufgeteilt — **Allgemein**, **HR** und **Sensoren** — auswählbar über das Abschnitts-Dropdown oben auf der Seite. Jede Seite hat ihre eigenen Speichern- und Verwerfen-Buttons; ein Wechsel zu einem anderen Abschnitt mit ungespeicherten Änderungen fragt vorab zur Bestätigung nach.

## Verwandte Artikel

- [Systemeinrichtung](/docs/admin-guide/system-setup)
- [Architektur](/docs/admin-guide/architecture)
- [Digital Signage](/docs/admin-guide/digital-signage)
- [Personio-Integration](/docs/admin-guide/personio)
- [Sensor Monitor](/docs/admin-guide/sensor-monitor)
- [Benutzerverwaltung](/docs/admin-guide/user-management)
