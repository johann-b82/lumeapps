# Qualitäts-Dashboard

Die Qualitäts-Perspektive bündelt drei Sichten auf die Qualitätslage: **Audits** (8D-Findings aus Audits), **Reklamationen** (On-Quality-Quote und Reklamationslisten) und **Qualitätsprüfung** (Anzahl geprüfter Produkte pro Prüfer-Tag). Oben links schaltest du mit dem Segment-Umschalter zwischen den drei Sichten um; je nach Sicht erscheinen daneben passende Filter. Alle drei Sichten reagieren auf den Zeitraumfilter der Seite.

Du erreichst die Perspektive über die Kachel **Qualität** im KPI-Dashboard (Route `/quality`).

## Audits

Diese Sicht zählt Audit-Findings nach Schweregrad. Rechts oben filterst du über die Checkbox-Gruppe **Audit-Arten** — Behördenaudit (BH AUD), Unterlieferanten-Audit (EX AUD), Internes Audit (IN AUD) und Kundenaudit (KU AUD). Alle vier sind vorausgewählt; das Abwählen einer Art entfernt deren Findings aus allen Kennzahlen.

**Kennzahl-Kacheln:** zwei Kacheln — **Audit-Findings Level 1** und **Audit-Findings Level 2**. Beide zeigen Delta-Badges gegenüber Vorperiode und Vorjahr, sobald ein Vergleichszeitraum vorliegt.

**Diagramme:** zwei Balkendiagramme — *Audit-Findings Level 1 nach Kategorie* und *Level 2 nach Kategorie*. Über die Schaltflächen **−** / **+** wechselst du die Granularität (Woche / Monat / Quartal / Jahr), mit **Zoom** begrenzt du die Y-Achse. Ist in den Einstellungen ein Zielwert hinterlegt, erscheint eine gestrichelte **Soll**-Linie.

**Findings-Übersicht (Tabelle):** eine Zeile je 8D-Report, durchsuchbar und sortierbar. Spalten: Nr., Datum, Kategorie, Level, Aussteller, Quelle (Kunde/Lieferant), Bezeichnung, Status (farbige Ampel).

## Reklamationen

Diese Sicht zeigt die On-Quality-Quote. Rechts oben wählst du die **Reklamationsart** — Kunde, Intern, Material Lieferanten oder Werkbänke — und mit dem **Mengen-Modus**-Umschalter, ob der Zähler die gesamte **Menge** oder nur die **Akzeptierte Menge** verwendet.

**Kennzahl-Kacheln:** drei Kacheln — **On Quality** (in %, Kachel-Beschriftung je nach Reklamationsart; darunter als Untertitel die Fehlerquote, Delta-Badges rechnen im On-Quality-Raum), **Gelieferte Stück** (Nenner) und **Reklamierte Stück** bzw. **Akzeptierte Reklamationsmenge** (Zähler, je nach Mengen-Modus).

**Diagramm:** ein Balkendiagramm des On-Quality-Verlaufs mit denselben Granularitäts- und Zoom-Schaltflächen und optionaler Soll-Linie.

**Reklamationsliste (Tabelle):** Titel je nach Art (z. B. *Kundenreklamationen*, *Lieferantenreklamationen*). Spalten: Nr., Datum, Quelle, Bezeichnung, Menge, Akz. Menge, Aussteller, Status.

## Qualitätsprüfung

Diese Sicht misst, wie viele Produkte geprüft wurden — normiert als **Produkte/Tag/Mitarbeiter** (geprüfte Menge geteilt durch Prüfer × Prüftage im Zeitraum). Datengrundlage ist der ERP-Export **AswQs2151**: eine Zeile je Qualitätsprüfungs-Buchung. Beim Einlesen wird jedes Produkt automatisch als **groß** oder **klein** klassifiziert (klein u. a. bei Literature Pocket, Riemen/Straps, Netz-Varianten, Life-Vest-/Stowage-Pouch sowie allen Diehl-Produktgruppen; alles andere gilt als groß). Nur Buchungen mit dem Kostenschlüssel „70000" zählen als echte Prüfung; Werkzeug-Zeilen werden verworfen.

**Kennzahl-Kacheln:** **Große Produkte (geprüft)** und **Kleine Produkte (geprüft)**, jeweils mit der Einheit *Produkte/Tag/Mitarbeiter* und Delta-Badges.

**Diagramme:** zwei Balkendiagramme — *Große Produkte im Zeitverlauf* und *Kleine Produkte im Zeitverlauf* — mit Granularitäts- und Zoom-Schaltflächen. Ist ein Zielwert hinterlegt (Standard: 150 groß / 400 klein), erscheint eine gestrichelte Soll-Linie.

**Prüfvorgänge (Tabelle):** eine Zeile je Buchung, filterbar nach Klasse (Alle / Große / Kleine) und durchsuchbar. Spalten: KPI-Häkchen, Datum (mit Zeit), Benutzer, FA, Artikel, Bezeichnung, Klasse, Produktgruppe, Menge, Ausschuss. Über das Häkchen in der ersten Spalte schließt du einzelne Fehlbuchungen aus der KPI aus (ausgeschlossene Zeilen bleiben durchgestrichen sichtbar, und Kacheln sowie Diagramme rechnen sofort neu). Das Ändern ist Admins vorbehalten.

**Daten hochladen:** Die Qualitätsprüfung speist sich aus der Datei `AswQs2151.txt` (tab-separiert, Windows-1252). Ziehe sie in das Ablagefeld oder wähle sie als Admin über **Durchsuchen** aus. Eine Anleitung findest du unter [Daten hochladen](/docs/user-guide/uploading-data).

## Zeitraum

Alle drei Sichten respektieren den Zeitraumfilter der Seite. Zeitraumvoreinstellungen und eigene Zeiträume sind unter [Filter &amp; Zeiträume](/docs/user-guide/filters) erklärt.
