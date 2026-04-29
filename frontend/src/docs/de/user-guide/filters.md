# Filter & Zeiträume

Im KPI Dashboard kannst du den Zeitraum und den Diagrammtyp für jedes Dashboard anpassen. Dieser Artikel erklärt den Datumsfilter, die Diagrammtyp-Auswahl und das Verhalten der Delta-Badges.

## Datumsfilter

Der Datumsfilter erscheint oben im **Umsatz-Dashboard**. Er ist als Segmented Control mit vier Voreinstellungen gestaltet:

| Voreinstellung | Angezeigter Zeitraum |
|---|---|
| **Diesen Monat** | Daten vom ersten Tag des aktuellen Kalendermonats bis heute |
| **Dieses Quartal** | Daten ab Quartalsbeginn (Q1 = Jan, Q2 = Apr, Q3 = Jul, Q4 = Okt) |
| **Dieses Jahr** | Daten vom 1. Januar des aktuellen Jahres bis heute |
| **Gesamt** | Alle Daten in der Datenbank, unabhängig vom Datum |

Die Standardauswahl ist **Diesen Monat**. Deine Auswahl bleibt bestehen, solange du im Umsatz-Dashboard bleibst, und wird beim Navigieren zurückgesetzt.

> **Hinweis:** Der Datumsfilter gilt ausschliesslich für das Umsatz-Dashboard. Das HR-Dashboard zeigt Daten immer relativ zum aktuellen Datum und verfügt über keinen Datumsfilter.

## Diagrammtyp

### Umsatz-Dashboard — Umsatzverlauf

Oben rechts im Diagramm "Umsatz über Zeit" kannst du zwischen zwei Ansichten wechseln:

- **Balken** — Ein Balkendiagramm (Standard). Die Balken werden nach der Granularität des gewählten Zeitraums gruppiert.
- **Fläche** — Ein gefülltes Flächendiagramm. Hilfreich, um Gesamttrends auf einen Blick zu erkennen.

### HR-Dashboard — HR-Diagramme

Im HR-Dashboard hat jedes Diagramm oben rechts eine eigene Diagrammtyp-Auswahl:

- **Fläche** — Ein gefülltes Flächendiagramm (Standard).
- **Balken** — Ein Balkendiagramm.

## Verhalten der Delta-Badges

Delta-Badges erscheinen auf den KPI-Karten und zeigen an, wie sich der aktuelle Zeitraum im Vergleich zu einem Referenzzeitraum entwickelt hat. Welche Badges angezeigt werden, hängt von der aktiven Voreinstellung ab:

| Aktive Voreinstellung | Angezeigte Badges |
|---|---|
| **Diesen Monat** | vs. Vormonat · vs. gleichem Monat im Vorjahr |
| **Dieses Quartal** | vs. Vorquartal · vs. gleichem Quartal im Vorjahr |
| **Dieses Jahr** | vs. Vorjahr YTD (nur ein Badge) |
| **Gesamt** | Keine Badges |

Eine vollständige Erklärung der Delta-Berechnung findest du im Artikel [Umsatz-Dashboard](sales-dashboard).

## Verwandte Artikel

- [Umsatz-Dashboard](sales-dashboard)
- [HR-Dashboard](hr-dashboard)
