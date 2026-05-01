# Personio-Integration

## Uebersicht

Personio ist die HR-Datenquelle fuer Abwesenheitsquoten, Mitarbeiterzahlen und Skill-Tracking-KPIs. Das KPI Dashboard verbindet sich ueber die Personio-API mit Ihrer Personio-Instanz, synchronisiert Mitarbeiter- und Abwesenheitsdaten und berechnet daraus HR-KPIs wie Krankheitsquote, Umsatz / Produktions-MA und Kompetenzentwicklung.

## Zugangsdaten eingeben

1. Öffnen Sie **Einstellungen → HR** — wählen Sie **HR** aus dem Abschnitts-Dropdown oben auf der Einstellungs-Seite. HR ist eine eigene Seite; Sie scrollen nicht mehr an Allgemein vorbei.
2. Im Abschnitt **Personio**:
3. Geben Sie Ihre **Client ID** in das erste Feld ein.
4. Geben Sie Ihr **Client Secret** in das zweite Feld ein.
5. Klicken Sie auf **Verbindung testen**, um die Zugangsdaten gegen die Personio-API zu pruefen, bevor Sie speichern.
6. Wenn der Test erfolgreich ist, klicken Sie auf **Aenderungen speichern**, um die Zugangsdaten zu sichern.

Beide Felder sind schreibgeschuetzte Passwortfelder -- zuvor gespeicherte Werte werden nicht angezeigt, nur ein Hinweis, dass Zugangsdaten hinterlegt sind.

> **Hinweis:** Behandeln Sie API-Zugangsdaten als Geheimnisse. Sie werden in der Anwendungsdatenbank gespeichert -- stellen Sie sicher, dass Ihre PostgreSQL-Instanz abgesichert ist.

## Sync-Intervall konfigurieren

Waehlen Sie im Dropdown **Sync-Intervall** neben den Zugangsdatenfeldern, wie oft Daten von Personio abgerufen werden:

| Option          | Verhalten                                          |
|-----------------|----------------------------------------------------|
| Nur manuell     | Daten werden nur abgerufen, wenn Sie "Daten aktualisieren" klicken |
| Stuendlich      | Automatische Synchronisierung jede Stunde          |
| Alle 6 Stunden  | Automatische Synchronisierung viermal taeglich     |
| Taeglich        | Automatische Synchronisierung alle 24 Stunden      |
| Woechentlich    | Automatische Synchronisierung einmal pro Woche     |

Waehlen Sie das Intervall, das zu Ihren Reporting-Anforderungen passt, und klicken Sie auf **Aenderungen speichern**.

## Felder zuordnen

Nachdem die Zugangsdaten gespeichert und verifiziert wurden, stehen drei Zuordnungsbereiche zur Verfuegung. Die Optionen in jeder Liste werden live aus Ihrer Personio-Instanz abgerufen.

### Krankheitstyp

Waehlen Sie einen oder mehrere Abwesenheitstypen aus der Liste. Diese werden zur Berechnung der **Krankheitsquote** auf dem HR-Dashboard verwendet. Nur in Ihrer Personio-Instanz definierte Abwesenheitstypen erscheinen hier.

### Produktions-Abteilung

Waehlen Sie eine oder mehrere Abteilungen, die als Produktionsabteilungen zaehlen. Diese werden zur Berechnung des KPIs **Umsatz / Produktions-MA** verwendet, der den Gesamtumsatz durch die Anzahl aktiver Mitarbeiter in den ausgewaehlten Abteilungen teilt.

### Skill-Attribut-Schluessel

Waehlen Sie eines oder mehrere benutzerdefinierte Attribute aus Personio, die Mitarbeiter-Skills repraesentieren. Diese werden fuer den KPI **Kompetenzentwicklung** verwendet, der die Entwicklung der Skill-Abdeckung ueber die Zeit verfolgt.

## Manuelle Synchronisierung

Klicken Sie im [HR-Dashboard](/docs/user-guide/hr-dashboard) auf die Schaltflaeche **Daten aktualisieren**, um eine sofortige Synchronisierung ausserhalb des geplanten Intervalls auszuloesen. Dies ruft die neuesten Daten von Personio ab, unabhaengig vom konfigurierten Sync-Zeitplan.

## Vertriebsabteilung (Vertriebler-KPI-Zuordnung)

Unter dem Picker für die Produktionsabteilung steht ein zweiter Picker — **Vertriebsabteilung**. Er steuert die vier Vertriebsaktivitäts-Diagramme und die Karte „Auftragsverteilung" auf dem Sales-Dashboard. Bei jedem Personio-Sync wird pro Mitarbeiter in der konfigurierten Vertriebsabteilung eine automatische Zuordnungszeile erzeugt, die den (großgeschriebenen + umlaut-gefalteten) Nachnamen — `Müller → MUELLER` — auf den `Wer`-Token aus der Kontakte-Datei abbildet.

Lässt sich der `Wer`-Token nicht aus dem Nachnamen ableiten (z. B. Spitznamen wie `GUENNI`), kann ein Administrator unter **Vertriebler-Zuordnungen** auf derselben Seite eine manuelle Zuordnung anlegen. Manuelle Zeilen überleben Sync-Läufe; automatische Zeilen werden vom Sync verwaltet und sind mit einem Schloss-Symbol schreibgeschützt.

Die Vertriebs-Diagramme und die Auftragsverteilungs-Karte bleiben leer, solange keine Kontakte-Datei hochgeladen **und** keine Vertriebsabteilung hier konfiguriert ist.

## Verwandte Artikel

- [HR-Dashboard](/docs/user-guide/hr-dashboard) -- die von Personio-Daten gespeisten KPIs anzeigen
- [Umsatz-Dashboard](/docs/user-guide/sales-dashboard) -- die vier Vertriebsaktivitäts-Diagramme und die Auftragsverteilungs-Karte, die aus der obigen Konfiguration gespeist werden
- [Architektur](/docs/admin-guide/architecture) -- verstehen, wie der Sync-Dienst ins System passt
