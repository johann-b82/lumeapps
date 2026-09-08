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

Diese Sicht misst, wie viele Produkte geprüft wurden — als **Tagesrate**. Zwei Kennzahlen je Klasse: **Teile pro Person und Tag** = geprüfte Menge ÷ Anzahl der (Prüfer, Prüftag)-Kombinationen, und **Teile pro Tag gesamt** = geprüfte Menge ÷ Anzahl Prüftage. Der Nenner wird **je Klasse getrennt** gebildet, „gesamt" bekommt einen eigenen Nenner über alle Zeilen — deshalb ergibt groß + klein **nicht** gesamt. Weil der Wert eine Tagesrate ist, ändern Woche/Monat/Quartal/Jahr nur, über wie viele Tage gemittelt wird; die Balken bleiben untereinander vergleichbar. Datengrundlage ist der ERP-Export **AswQs2151**: eine Zeile je Qualitätsprüfungs-Buchung. Beim Einlesen wird jedes Produkt automatisch als **groß** oder **klein** klassifiziert (klein u. a. bei Literature Pocket, Riemen/Straps, Netz-Varianten, Life-Vest-/Stowage-Pouch sowie allen Diehl-Produktgruppen; alles andere gilt als groß). Nur Buchungen mit dem Kostenschlüssel „70000" zählen als echte Prüfung; Werkzeug-Zeilen werden verworfen.

**Artikel-Auswahl:** oben rechts schaltest du zwischen **Fertigartikel** (Standard; alle Artikel ohne „H" am Anfang), **Halbfertigartikel** (nur Artikel mit „H", z. B. Zwischenprüfungen) und **Alle Artikel**. So lassen sich Prüfer ausblenden, die nur wegen gebuchter Zwischenprüfungen erscheinen (die Zwischenprüfung ist nötig, damit der Artikel weitergebucht werden kann). Der Filter wirkt auf Kacheln, Diagramme und die Prüfvorgänge-Tabelle.

**Kennzahl-Kacheln:** drei Kacheln — **Große**, **Kleine** und **Gesamt** — mit dem Hauptwert *Teile/Person/Tag*, dem Untertitel *Teile/Tag gesamt* und Delta-Badges.

**Diagramme:** drei Balkendiagramme — *Große*, *Kleine* und *Gesamt im Zeitverlauf* — mit gemeinsamen Granularitäts- und Zoom-Schaltflächen. Der Balkenwert ist *Teile/Person/Tag*; der Tooltip zeigt zusätzlich Teile/Tag gesamt, Teile absolut, Personen-Tage und Prüftage. Eine gestrichelte Soll-Linie erscheint nur, wenn ein Zielwert hinterlegt ist (kein Standardwert mehr — die früheren 150/400 waren für die korrigierte Tagesrate unerreichbar; neue Zielwerte legt das Qualitätswesen fest). Hinweis: „Klein" ist auf Wochenebene wenig aussagekräftig — kleinste sinnvolle Granularität ist der Monat.

**Prüfvorgänge (Tabelle):** eine Zeile je Buchung, filterbar nach Klasse (Alle / Große / Kleine) und durchsuchbar. Spalten: KPI-Häkchen, Datum (mit Zeit), Benutzer, FA, Artikel, Bezeichnung, Klasse, Produktgruppe, Menge, Ausschuss. Über das Häkchen in der ersten Spalte schließt du einzelne Fehlbuchungen aus der KPI aus (ausgeschlossene Zeilen bleiben durchgestrichen sichtbar, und Kacheln sowie Diagramme rechnen sofort neu). Das Ändern ist Admins vorbehalten.

**Daten hochladen:** Die Qualitätsprüfung speist sich aus der Datei `AswQs2151.txt` (tab-separiert, Windows-1252). Ziehe sie in das Ablagefeld oder wähle sie als Admin über **Durchsuchen** aus. Eine Anleitung findest du unter [Daten hochladen](/docs/user-guide/uploading-data).

## Zeitraum

Alle drei Sichten respektieren den Zeitraumfilter der Seite. Zeitraumvoreinstellungen und eigene Zeiträume sind unter [Filter &amp; Zeiträume](/docs/user-guide/filters) erklärt.
