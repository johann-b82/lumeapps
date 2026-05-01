# Umsatz-Dashboard

Das Umsatz-Dashboard gibt dir einen aktuellen Überblick über deine Umsatzentwicklung. Es kombiniert drei KPI-Übersichtskacheln, einen „Umsatzverlauf"-Diagrammbereich und eine durchsuchbare Auftragstabelle — alles nach Zeitraum filterbar. Dieser Artikel erklärt die einzelnen Bereiche und die Bedeutung der angezeigten Daten.

## KPI-Kacheln

Am oberen Rand des Dashboards zeigen drei Kacheln deine wichtigsten Kennzahlen für den ausgewählten Zeitraum:

- **Gesamtumsatz** — Die Summe aller Auftragswerte in EUR.
- **Durchschnittlicher Auftragswert** — Gesamtumsatz geteilt durch die Anzahl der Aufträge, in EUR.
- **Aufträge gesamt** — Die Anzahl aller Aufträge im gewählten Zeitraum.

> **Hinweis:** Aufträge mit Wert 0 € werden bei allen drei Kennzahlen nicht berücksichtigt.

### Delta-Badges

Jede Kachel zeigt ein oder zwei Delta-Badges, die den aktuellen Zeitraum mit einem Referenzzeitraum vergleichen:

- **Diesen Monat** — Zwei Badges: vs. Vormonat und vs. Vorjahresmonat.
- **Dieses Quartal** — Zwei Badges: vs. Vorquartal und vs. Vorjahr.
- **Dieses Jahr** — Ein Badge: vs. Vorjahr (Jahr-zu-dato-Vergleich).
- **Gesamter Zeitraum** — Keine Delta-Badges.
- **Benutzerdefiniert** — Keine Delta-Badges.

Falls kein Vergleichszeitraum verfügbar ist, zeigt das Badge den Tooltip: „Kein Vergleichszeitraum verfügbar".

## Umsatzverlauf-Diagramm

Unterhalb der KPI-Kacheln visualisiert das Diagramm **Umsatzverlauf** die Umsätze im gewählten Zeitraum.

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

## Auftragstabelle

Unterhalb des Diagramms listet die Tabelle **Aufträge** alle Aufträge im gewählten Zeitraum. Du kannst:

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

## Vertriebsaktivität

Unter dem Umsatzverlauf zeigt die Karte **Vertriebsaktivität** vier wöchentliche Liniendiagramme — eines pro KPI, mit einer Linie pro Vertriebler:

| KPI | Was gezählt wird |
|-----|------------------|
| Erstkontakte | Neue Leads (Typ = ERS in der Kontakte-Datei) |
| Interessenten | Frühe Vertriebsgespräche (Typ ∈ {ANFR, EPA}) |
| Besuche | Vor-Ort-Termine beim Kunden (Typ = ORT) |
| Angebote | Im Kontakt erfasste Angebote (Kommentar beginnt mit „Angebot") |

Die Vertriebler kommen direkt aus der Spalte `Wer` der hochgeladenen Kontakte-Datei (z. B. `KARRER`, `GUENDEL`). Eine Personio-Zuordnung wird nicht verwendet.

Alle vier Diagramme respektieren den Zeitraumfilter des Dashboards und verwenden pro Vertriebler dieselbe Farbe — eine Person liest sich also auf allen vier Diagrammen als dieselbe Linie.

## Auftragsverteilung

Unter den Aktivitäts-Diagrammen zeigt die Karte **Auftragsverteilung** drei Zahlen für den gewählten Zeitraum:

| Kennzahl | Bedeutung |
|----------|-----------|
| Aufträge / Woche / Vertriebler | Durchschnittliche Auftragsanzahl pro Vertriebler pro Woche. Aufträge werden über Kontakte-Zeilen einem Vertriebler zugeordnet, deren Kommentar die Auftragsnummer nennt („Angebot 5000000"). |
| Top-3-Kunden-Anteil | Anteil des Auftragsvolumens, der auf die drei umsatzstärksten Kunden entfällt. Der Untertitel listet diese Kunden auf. |
| Restkunden | 100 % minus Top-3-Anteil — der Long-Tail-Anteil am Umsatz. |

Beide Karten bleiben leer, solange keine Kontakte-Datei hochgeladen wurde.

## Verwandte Artikel

- [Filter & Zeiträume](/docs/user-guide/filters) — Vollständige Erklärung der Zeitraumvoreinstellungen, benutzerdefinierten Zeiträume und Diagrammsteuerung.
- [HR-Dashboard](/docs/user-guide/hr-dashboard) — HR-Kennzahlen neben deinen Umsatzdaten einsehen.
- [Daten hochladen](/docs/user-guide/uploading-data) — Neue Umsatzdaten ins Dashboard laden.
