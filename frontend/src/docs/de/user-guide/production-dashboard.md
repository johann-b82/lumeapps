# Produktions-Dashboard

Die Produktions-Perspektive zeigt, wie termintreu deine Aufträge ausgeliefert werden. Der erste Abschnitt **Aufträge in Verzug** kombiniert oben vier Kennzahl-Kacheln, darunter den Verzugsquote-Verlauf und zwei Tabellen: die zu spät gelieferten Aufträge sowie die überfälligen, noch offenen Aufträge. Alles ist nach Zeitraum filterbar.

![Produktions-Perspektive: Kennzahlen und Verlauf mit Ziellinie](/docs/produktion-uebersicht.png)

Du erreichst die Perspektive über die Kachel **Produktion** auf der Startseite oder über den Perspektiven-Umschalter oben links.

## Was zählt als „in Verzug"?

Ein Auftrag wird dem Zeitraum seines **Zieltermins** zugeordnet (dem spätesten geplanten Lieferdatum seiner Positionen). Innerhalb des gewählten Zeitraums zählt ein Auftrag, sobald sein Ausgang feststeht, und gilt als **in Verzug**, wenn eine der beiden Bedingungen zutrifft:

- **Zu spät geliefert** — der Auftrag hat einen Lieferschein, und die letzte Lieferung erfolgte nach dem Zieltermin.
- **Überfällig & offen** — der Auftrag hat noch keinen Lieferschein, und der Zieltermin liegt bereits in der Vergangenheit.

Aufträge, deren Zieltermin noch in der Zukunft liegt und die noch nicht geliefert sind, sind **offen** und werden weder als in Verzug noch im Nenner mitgezählt — ihr Ausgang steht noch nicht fest.

## Kennzahl-Kacheln

- **Verzugsquote** — Anteil der im Zeitraum fälligen Aufträge, die zu spät geliefert oder überfällig offen sind. Niedriger ist besser.
- **Aufträge in Verzug** — Anzahl der Aufträge in Verzug (zu spät geliefert **plus** überfällig offen).
- **Aufträge gesamt** — Anzahl der im Zeitraum fälligen Aufträge (der Nenner der Quote).
- **Ø Verzug** — durchschnittliche Verspätung in Tagen.

Die Verzugsquote-Kachel zeigt Delta-Badges gegenüber Vorperiode und Vorjahr, sobald ein Vergleichszeitraum vorliegt. Da eine **niedrige** Quote gut ist, wird eine Verbesserung grün dargestellt.

## Verzugsquote im Zeitverlauf

Das Balkendiagramm zeigt die Verzugsquote je Zeitabschnitt. Mit den Schaltflächen **−** / **+** oben rechts wechselst du die Granularität (Woche / Monat / Quartal / Jahr); über die Von-/Bis-Felder wählst du einen eigenen Zeitraum.

### Einstellbare Ziellinie

Ist in den Einstellungen ein Zielwert hinterlegt, erscheint im Diagramm eine gestrichelte **Ziellinie** (z. B. `Ziel 2,0 %`). Balken oberhalb der Linie überschreiten das Ziel.

Den Wert legst du unter **Einstellungen → Produktion → Max. Verzugsquote** fest (in Prozent). Ein leeres Feld blendet die Linie aus.

![Einstellung der Ziellinie unter Einstellungen → Produktion](/docs/produktion-ziellinie.png)

## Die zwei Tabellen

Unter dem Diagramm stehen zwei Tabellen nebeneinander. Zusammen ergeben sie die Aufträge in Verzug — nach Kategorie getrennt. Beide sind durchsuchbar und über die Spaltenköpfe sortierbar.

![Tabellen: Aufträge in Verzug und überfällige offene Aufträge](/docs/produktion-tabellen.png)

- **Aufträge in Verzug** — die zu spät gelieferten Aufträge, absteigend nach Verzugstagen. Spalten: Auftrag, Kunde, Zieltermin, Ist-Lieferung, Verzug (Tage).
- **Überfällige offene Aufträge** — die noch nicht gelieferten Aufträge, deren Zieltermin bereits überschritten ist — die akute Handlungsliste. Spalten: Auftrag, Kunde, Zieltermin, Tage überfällig.

## Daten einspielen

Die Perspektive speist sich aus zwei Exporten, die du über die Upload-Seite einspielst:

- **Auftragspositionen (AUF, positionsgenau)** — liefert die Zieltermine je Auftragsposition.
- **Lieferungen (Lieferscheine)** — liefert die Ist-Lieferdaten.

Eine Anleitung zum Hochladen findest du unter [Daten hochladen](/docs/user-guide/uploading-data). Zeitraumvoreinstellungen und eigene Zeiträume sind unter [Filter & Zeiträume](/docs/user-guide/filters) erklärt.
