# Einkauf-Dashboard

Die Einkauf-Perspektive zeigt, wie termintreu deine Lieferanten liefern. Der erste Abschnitt **Liefertermintreue (OTD)** kombiniert oben vier Kennzahl-Kacheln, darunter den OTD-Verlauf als Balkendiagramm und eine Prüftabelle mit allen Lieferpositionen im Zeitraum. Alles ist nach Zeitraum filterbar.

Du erreichst die Perspektive über die Kachel **Einkauf** im KPI-Dashboard (Route `/procurement`) oder über den Abschnitts-Umschalter im Seitenheader. Weitere Abschnitte (On Quality – Werkbänke, Material-Lieferanten) sind geplant und docken später hier an.

## Was zählt als „pünktlich"?

Bewertet wird je **Lieferposition** – nicht nach Menge. Eine Position gilt als **pünktlich**, wenn ihr Verzug (`Verzug in Tagen`) null oder negativ ist, also am oder vor dem bestätigten Zieltermin geliefert wurde (früh zählt ebenfalls als pünktlich). Der Zeitraumfilter greift auf das **Ist-Lieferdatum** (tatsächlicher Wareneingang), damit die OTD-Quote zum selben Zeitfenster wie die übrigen KPIs passt.

Die OTD-Quote ist der Anteil pünktlicher Positionen an allen Positionen im Zeitraum. **Höher ist besser** – anders als bei der Reklamationsquote.

## Kennzahl-Kacheln

- **OTD-Quote** – Anteil pünktlich gelieferter Positionen. Zeigt Delta-Badges gegenüber Vorperiode und Vorjahr, sobald ein Vergleichszeitraum vorliegt. Da eine **hohe** Quote gut ist, wird eine Verbesserung grün dargestellt.
- **Pünktliche Positionen** – Anzahl pünktlicher Positionen (der Zähler der Quote).
- **Gesamt-Positionen** – Anzahl aller Positionen im Zeitraum (der Nenner).
- **Ø Verzug** – durchschnittliche Verspätung in Tagen über die Positionen des Zeitraums.

## OTD-Quote im Zeitverlauf

Das Balkendiagramm zeigt die OTD-Quote je Zeitabschnitt. Mit den Schaltflächen **−** / **+** oben rechts wechselst du die Granularität (Woche / Monat / Quartal / Jahr); die Voreinstellung richtet sich automatisch nach dem gewählten Zeitraum. Über die Von-/Bis-Felder wählst du direkt im Diagrammkopf einen eigenen Zeitraum – Kacheln, Diagramm und Tabelle bleiben synchron.

Eine gestrichelte **Ziellinie** markiert das feste Ziel von `98,0 %`. Balken unterhalb der Linie verfehlen das Ziel.

## Prüftabelle

Die Tabelle listet eine Zeile je Lieferposition im Zeitraum. Sie ist über das Suchfeld durchsuchbar (Auftrag, Lieferant, Adress-Nr., Artikelnummer, Artikelname), über die Spaltenköpfe sortierbar und seitenweise blätterbar (50 Zeilen pro Seite). Die Verzugs-Spalte ist eingefärbt: ≤ 0 Tage pünktlich (grün), &gt; 0 Tage verspätet (rot).

| Spalte | Beschreibung |
|--------|-------------|
| Auftrag | Auftragsnummer der Position |
| Lieferant | Lieferantenname (mit Adress-Nr. in Klammern) |
| Artikel | Artikelname bzw. Artikelnummer |
| Ist-Lieferung | Tatsächliches Lieferdatum (Wareneingang) |
| Zieltermin | Bestätigter Zieltermin |
| Verzug | Verzug in Tagen (+ verspätet, − früh) |
| Menge | Gelieferte Menge |

## Daten einspielen

Die Perspektive speist sich aus einem Liefertermintreue-Export, den du über die Upload-Seite einspielst. Er liefert je Lieferposition Ist-Lieferdatum, Zieltermin und Verzug.

Eine Anleitung zum Hochladen findest du unter [Daten hochladen](/docs/user-guide/uploading-data). Zeitraumvoreinstellungen und eigene Zeiträume sind unter [Filter &amp; Zeiträume](/docs/user-guide/filters) erklärt.
