# HR-Dashboard

Das HR-Dashboard zeigt Personalwirtschafts-KPIs, die direkt aus Personio gespeist werden. Es umfasst fünf Kennzahlen-Kacheln, Verlaufsdiagramme und eine detaillierte Mitarbeitertabelle. Dieser Artikel erklärt die einzelnen Bereiche und zeigt, was zu tun ist, wenn das Dashboard keine Daten anzeigt.

## Voraussetzung: Personio-Verbindung

HR-Daten werden direkt aus Personio abgerufen. Der Zustand des Dashboards hängt davon ab, ob Personio konfiguriert und synchronisiert ist:

- **Nicht konfiguriert** — Jede KPI-Kachel zeigt „—" mit der Beschriftung „nicht konfiguriert" und einem Link zu **Einstellungen öffnen**. Navigiere zu den Einstellungen, um deine Personio Client-ID und dein Client-Secret einzugeben.
- **Konfiguriert, noch nicht synchronisiert** — Ein Banner erscheint: „Noch keine Daten synchronisiert — Klicke auf 'Daten aktualisieren' oder konfiguriere die automatische Synchronisation in den Einstellungen." Löse eine manuelle Synchronisation aus oder stelle ein Auto-Sync-Intervall in den Einstellungen ein.
- **Synchronisierungsfehler** — Ein rotes Banner zeigt „KPIs konnten nicht geladen werden". Prüfe deine Verbindung und klicke auf **Daten aktualisieren**.
- **Konfiguriert mit Daten** — KPI-Kacheln zeigen aktuelle Werte mit Delta-Badges.

## Daten synchronisieren

Die Schaltfläche **Daten aktualisieren** im Seitenheader löst eine manuelle Personio-Synchronisation aus. Nach dem Klicken:

1. Die Schaltfläche zeigt einen Ladezustand, während die Synchronisation läuft.
2. Bei Erfolg erscheint eine Toast-Meldung: „Synchronisierung abgeschlossen".
3. Bei Fehler erscheint: „Synchronisierung fehlgeschlagen". Prüfe deine Personio-Zugangsdaten in den Einstellungen.

Im Header wird außerdem die letzte Synchronisierungszeit angezeigt: **Letzte Synchronisierung: {Datum und Uhrzeit}**, oder „Noch nicht synchronisiert", wenn noch keine Synchronisation stattgefunden hat.

## KPI-Kacheln

Fünf KPI-Kacheln sind in einem 3+2-Layout angeordnet:

| KPI | Einheit | Beschreibung |
|-----|---------|-------------|
| Überstunden-Quote | % | Überstunden geteilt durch die Gesamtarbeitsstunden aktiver Mitarbeiter |
| Krankheitsquote | % | Anteil der Arbeitszeit, der durch Krankheitstage ausgefallen ist |
| Fluktuation | % | Mitarbeiterfluktuation |
| Kompetenzentwicklung | % | Anteil der Mitarbeiter mit skill-bezogenen Attributen |
| Umsatz / Produktions-MA | EUR | Umsatz pro Produktionsmitarbeiter |

### Delta-Badges

Jede Kachel zeigt zwei Delta-Badges: vs. Vormonat und vs. Vorjahr. Das HR-Dashboard verwendet das aktuelle Datum als Referenzpunkt — es gibt keinen Zeitraumfilter auf dieser Seite. Falls kein Vergleichszeitraum verfügbar ist, zeigt das Badge den Tooltip: „Kein Vergleichszeitraum verfügbar".

## Verlaufsdiagramme

Unterhalb der KPI-Kacheln zeigt der Diagrammbereich Verlaufskurven für jeden HR-KPI über die Zeit.

- Mit dem **Fläche** / **Balken**-Umschalter wechselst du den Diagrammtyp.
- Die Diagramme aktualisieren sich automatisch nach jeder Personio-Synchronisation.

## Mitarbeitertabelle

Die Tabelle **Mitarbeiter** listet alle aus Personio abgerufenen Mitarbeiter.

- **Suchen** — Gib einen Begriff ins Suchfeld ein, um nach Name, Abteilung oder Position zu filtern.
- **Filtern** — Nutze die Filterschaltflächen, um **Alle**, **Aktive** oder **Mit Überstunden** anzuzeigen.

Tabellenspalten:

| Spalte | Beschreibung |
|--------|-------------|
| Name | Vollständiger Name des Mitarbeiters |
| Abteilung | Personio-Abteilung |
| Position | Berufsbezeichnung |
| Status | Aktiv / Inaktiv |
| Eintrittsdatum | Datum des Arbeitseintritts |
| Std./Woche | Vertragliche Wochenstunden |
| Ist-Std. | Tatsächlich geleistete Stunden |
| Überstunden | Anzahl der Überstunden |
| ÜS % | Überstunden als Anteil der Ist-Stunden |

> **Hinweis:** Das HR-Dashboard verfügt über keinen Zeitraumfilter. Alle Kennzahlen werden relativ zum aktuellen Datum berechnet, basierend auf den Daten der letzten Personio-Synchronisation. Informationen zum Zeitraumfilter für das Umsatz-Dashboard findest du unter [Filter & Zeiträume](/docs/user-guide/filters).

## Verwandte Artikel

- [Umsatz-Dashboard](/docs/user-guide/sales-dashboard) — Umsatz-KPIs mit Zeitraumfilter.
- [Filter & Zeiträume](/docs/user-guide/filters) — Zeitraumvoreinstellungen und Diagrammsteuerung (Umsatz-Dashboard).
- [Sprache & Dark Mode](/docs/user-guide/language-and-theme) — Anzeigesprache und Farbschema anpassen.
