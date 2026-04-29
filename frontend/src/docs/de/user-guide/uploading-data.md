# Daten hochladen

In diesem Artikel erfährst du, wie du eine Umsatzdatei hochlädst, was während der Verarbeitung passiert und wie du deinen Upload-Verlauf verwaltest. Das Hochladen von Daten ist der erste Schritt, um KPIs im Umsatz-Dashboard anzeigen zu lassen.

## Voraussetzungen

> **Hinweis:** Die Upload-Seite ist ausschließlich für Administratoren zugänglich. Wenn du die Meldung „Du hast keine Berechtigung, auf diese Seite zuzugreifen" siehst, fehlt dir die erforderliche Rolle. Bitte deinen Administrator, die Datei für dich hochzuladen.

Die Upload-Seite akzeptiert ausschließlich `.csv`- und `.txt`-Dateien.

> **Tipp:** Nur `.csv`- und `.txt`-Dateien werden akzeptiert. Excel-Dateien (`.xlsx`) werden auf der Upload-Seite nicht unterstützt.

## Datei hochladen

Du kannst eine Datei auf zwei Wegen hinzufügen:

1. **Drag-and-drop** — Ziehe deine Datei direkt auf die Drop-Zone. Der Rahmen wird hervorgehoben und der Hinweistext ändert sich, während du die Datei darüber hältst. Lasse die Datei los, um den Upload zu starten.

2. **Datei auswählen** — Klicke auf die Schaltfläche **Datei auswählen**, um den Dateibrowser zu öffnen. Wähle deine `.csv`- oder `.txt`-Datei aus und bestätige.

Der Upload beginnt sofort nach dem Ablegen oder Auswählen der Datei. Die Drop-Zone zeigt einen Ladeindikator mit dem Text „Wird verarbeitet...", während die Datei importiert wird. Navigiere in dieser Zeit nicht weg.

## Upload-Zustände

Nach Abschluss der Verarbeitung erscheint einer der folgenden Zustände:

- **Erfolg (vollständiger Import)** — Eine Toast-Meldung erscheint: „Datei hochgeladen" mit dem Hinweis `{Dateiname}: {Anzahl} Zeilen importiert`. Alle Zeilen wurden fehlerfrei importiert.

- **Erfolg (teilweiser Import)** — Die Toast-Meldung zeigt `{Dateiname}: {Anzahl} Zeilen importiert, {Fehler} Zeilen übersprungen`. Einige Zeilen enthielten Validierungsfehler. Unterhalb der Drop-Zone erscheint eine Fehlerliste mit den betroffenen Zeilen, den Spaltennamen und den jeweiligen Fehlermeldungen.

- **Nicht unterstütztes Dateiformat** — Eine rote Fehlermeldung erscheint: „Nicht unterstütztes Format: `{Erweiterung}`. Nur `.csv` und `.txt` erlaubt." Es werden keine Daten importiert. Konvertiere die Datei zunächst in das CSV-Format und versuche es erneut.

- **Netzwerkfehler** — Eine Fehler-Toast-Meldung erscheint mit der Fehlermeldung des Servers. Prüfe deine Verbindung und versuche es erneut.

## Fehlerliste lesen

Wenn Zeilen übersprungen wurden, erscheint unterhalb der Drop-Zone eine Fehlerliste mit der Überschrift **Importfehler ({{Anzahl}} Zeilen übersprungen)**. Jeder Eintrag zeigt:

- Die Zeilennummer
- Die fehlerhafte Spalte (sofern zutreffend)
- Eine Beschreibung des Fehlers

Nutze diese Liste, um die Quelldatei zu korrigieren und erneut hochzuladen. Die bereits importierten Zeilen bleiben in der Datenbank erhalten.

## Upload-Verlauf verwalten

Die Tabelle **Upload-Verlauf** auf der rechten Seite zeigt alle bisher hochgeladenen Dateien. Spalten:

| Spalte | Beschreibung |
|--------|-------------|
| Dateiname | Der ursprüngliche Dateiname |
| Hochgeladen am | Datum und Uhrzeit des Uploads |
| Zeilen | Anzahl der importierten Zeilen |
| Status | Ergebnis des Imports (Erfolg, teilweise, Fehler) |
| Fehler | Anzahl der übersprungenen Zeilen |

Um einen Upload und alle zugehörigen Datensätze zu löschen, klicke auf das Löschen-Symbol in der jeweiligen Zeile. Ein Bestätigungsdialog erscheint — klicke auf **Löschen**, um den Vorgang zu bestätigen, oder auf **Upload behalten**, um abzubrechen.

> **Hinweis:** Das Löschen eines Uploads entfernt dauerhaft alle Umsatzdatensätze, die aus dieser Datei stammen. Dieser Vorgang kann nicht rückgängig gemacht werden.

## Verwandte Artikel

- [Umsatz-Dashboard](/docs/user-guide/sales-dashboard) — Sieh deine hochgeladenen Daten als KPI-Kacheln und Diagramme.
- [Filter & Zeiträume](/docs/user-guide/filters) — Lerne, die Dashboard-Ansicht nach Zeitraum einzugrenzen.
