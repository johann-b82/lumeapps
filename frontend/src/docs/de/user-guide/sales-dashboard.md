# Umsatz-Dashboard

Das Umsatz-Dashboard gibt dir einen aktuellen Überblick über deine Vertriebsleistung. Es kombiniert oben sechs Übersichts­kacheln (drei Umsatz-KPIs sowie Aufträge / Woche / Vertriebler und ein Kundenanteils-Widget), darunter den Umsatzverlauf, die wöchentlichen Vertriebsaktivitäts-Balken pro Vertriebler und eine durchsuchbare Auftragstabelle — alles nach Zeitraum filterbar. Dieser Artikel erklärt jeden Bereich.

## KPI-Kacheln

Am oberen Rand des Dashboards zeigen drei Kacheln deine wichtigsten Kennzahlen für den ausgewählten Zeitraum:

- **Auftragswert** — Die Summe aller Auftragswerte im gewählten Zeitraum, in EUR. (Umbenannt von „Gesamtumsatz".)
- **Durchschnittlicher Auftragswert** — Auftragswert geteilt durch die Anzahl der Aufträge, in EUR.
- **Aufträge gesamt** — Die Anzahl aller Aufträge im gewählten Zeitraum.

> **Hinweis:** Aufträge mit Wert 0 € werden in jeder Kennzahl auf dem Umsatz-Dashboard ausgeschlossen — den drei KPI-Kacheln oben, **Aufträge / Woche / Vertriebler** und der Kundenanteils-Leiste.

### Delta-Badges

Jede Kachel zeigt ein oder zwei Delta-Badges, die den aktuellen Zeitraum mit einem Referenzzeitraum vergleichen:

- **Diesen Monat** — Zwei Badges: vs. Vormonat und vs. Vorjahresmonat.
- **Dieses Quartal** — Zwei Badges: vs. Vorquartal und vs. Vorjahr.
- **Dieses Jahr** — Ein Badge: vs. Vorjahr (Jahr-zu-dato-Vergleich).
- **Gesamter Zeitraum** / **Benutzerdefiniert** — Keine Delta-Badges.

Falls kein Vergleichszeitraum verfügbar ist, zeigt das Badge den Tooltip „Kein Vergleichszeitraum verfügbar".

## Auftragsverteilungs-Reihe

Direkt unter den drei oberen KPI-Kacheln zeigt eine zweite Reihe die Aufteilung der Aufträge pro Vertriebler und pro Kunde.

### Aufträge / Woche / Vertriebler

Die durchschnittliche Anzahl Aufträge pro Vertriebler pro Woche im gewählten Zeitraum. Zähler ist die Anzahl der Aufträge mit Wert > 0 €. Nenner ist die Anzahl unterschiedlicher Ersteller (abgeleitet aus der Kontakte-Datei — siehe „Vertriebsaktivität") multipliziert mit der Anzahl Wochen im Zeitraum. Wurde noch keine Kontakte-Datei hochgeladen, steht hier `0,0`.

### Kundenanteil + Top-3-Liste

Eine horizontale gestapelte Leiste zeigt, welchen Anteil die drei umsatzstärksten Kunden am Auftragsvolumen haben — gegenüber dem Rest. Jedes Segment trägt seine Prozentzahl im Inneren (Segmente unter 8 % verstecken die Inline-Beschriftung, um Überlauf zu vermeiden). Eine kleine Legende unter der Leiste wiederholt die Farbzuordnung.

Rechts daneben (oder darunter auf schmalen Viewports) zählt eine nummerierte Liste (1. / 2. / 3.) die Top-3-Kunden in absteigender Auftragswert-Reihenfolge auf.

Das Widget nutzt das Primärfarb-Token (`var(--primary)`) für das Top-3-Segment und das gedämpfte Hintergrund-Token (`var(--muted)`) für den Rest. Wird die Primärfarbe in den Einstellungen geändert, zieht das Top-3-Segment dynamisch nach. Auf dem Umsatz-Dashboard wird kein Rot verwendet.

## Umsatzverlauf-Diagramm

Unterhalb der Auftragsverteilungs-Reihe visualisiert das Diagramm **Umsatzverlauf** die Umsätze im gewählten Zeitraum.

- Mit dem **Balken** / **Fläche**-Umschalter oben rechts im Diagramm wechselst du den Diagrammtyp. Standardmäßig ist „Balken" ausgewählt.
- Bei Voreinstellungen mit Vergleichszeitraum (Diesen Monat, Dieses Quartal, Dieses Jahr) wird eine Vergleichsserie überlagert.
- Die x-Achse zeigt Kalenderwochen-Beschriftungen für „Diesen Monat" und Monat + Jahr für andere Voreinstellungen.

Eine vollständige Erklärung der Zeitraumvoreinstellungen, benutzerdefinierter Zeiträume und des Diagrammtyp-Umschalters findest du unter [Filter & Zeiträume](/docs/user-guide/filters).

## Zeitraumfilter

Der Zeitraumfilter befindet sich oben auf der Dashboard-Seite. Wähle eine der vier Voreinstellungen:

| Voreinstellung | Was angezeigt wird |
|----------------|-------------------|
| Diesen Monat | Aufträge im aktuellen Kalendermonat |
| Dieses Quartal | Aufträge im aktuellen Kalenderquartal |
| Dieses Jahr | Aufträge seit dem 1. Januar des aktuellen Jahres |
| Gesamter Zeitraum | Alle Aufträge in der Datenbank |

Die Standardauswahl ist **Diesen Monat**. Die Auswahl wird zurückgesetzt, wenn du das Dashboard verlässt.

## Vertriebsaktivität

Unter dem Umsatzverlauf zeigt die Karte **Vertriebsaktivität** vier wöchentliche **Balkendiagramme** — eines pro KPI. Jeder Balken stellt die Team-Summe der jeweiligen Woche in der Primärfarbe dar. Beim Hover (Balken wechselt zur gedämpften Farbe) zeigt ein Tooltip die Gesamtsumme sowie die Aufschlüsselung pro Vertriebler.

| KPI | Was gezählt wird |
|-----|------------------|
| Erstkontakte | Neue Leads (Typ = ERS in der Kontakte-Datei) |
| Interessenten | Frühe Vertriebsgespräche (Typ ∈ {ANFR, EPA}) |
| Besuche | Vor-Ort-Termine beim Kunden (Typ = ORT) |
| Angebote | Im Kontakt erfasste Angebote (Kommentar beginnt mit „Angebot") |

Die Vertriebler kommen direkt aus der Spalte `Wer` der hochgeladenen Kontakte-Datei (z. B. `KARRER`, `GUENDEL`). Eine Personio-Zuordnung wird nicht verwendet.

Alle vier Diagramme respektieren den Zeitraumfilter des Dashboards. Die Wochenlabels werden ohne Jahresangabe dargestellt (z. B. `KW 18`).

Die Diagramme bleiben leer, solange keine Kontakte-Datei hochgeladen wurde.

## Auftragstabelle

Unterhalb der Aktivitäts-Diagramme listet die Tabelle **Aufträge** alle Aufträge im gewählten Zeitraum. Du kannst:

- **Suchen** — Gib einen Begriff ins Suchfeld ein, um nach Auftrags-Nr., Kunde oder Projektname zu filtern.
- **Sortieren** — Klicke auf einen Spaltenkopf zum Sortieren.

Tabellenspalten:

| Spalte | Beschreibung |
|--------|-------------|
| Auftrags-Nr. | Die Auftragskennung |
| Kunde | Kundenname |
| Projekt | Projektname |
| Datum | Auftragsdatum |
| Gesamt | Gesamter Auftragswert (EUR) |
| Restwert | Offener Restbetrag (EUR) |

## Verwandte Artikel

- [Filter & Zeiträume](/docs/user-guide/filters) — Vollständige Erklärung der Zeitraumvoreinstellungen, benutzerdefinierten Zeiträume und Diagrammsteuerung.
- [HR-Dashboard](/docs/user-guide/hr-dashboard) — HR-Kennzahlen neben deinen Umsatzdaten einsehen.
- [Daten hochladen](/docs/user-guide/uploading-data) — Neue Umsatzdaten ins Dashboard laden.
