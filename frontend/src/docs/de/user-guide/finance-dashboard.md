# Finanz-Dashboard

Die Finanzperspektive zeigt, wie viel von deinem Umsatz für Material und Personal aufgeht. Über einen Umschalter oben wechselst du zwischen den beiden Kennzahlen **Material** und **Personal**. Jede Ansicht zeigt dieselbe Struktur: oben vier Kennzahl-Kacheln, darunter den Verlauf als Balkendiagramm und darunter eine Prüftabelle. Alles ist nach Zeitraum filterbar.

Du erreichst die Perspektive über die Kachel **Finanzperspektive** im KPI-Dashboard (Route `/finance`).

## Material und Personal umschalten

Der Umschalter oben (**Material** / **Personal**) bestimmt, welche Kennzahl du siehst. Beide Ansichten teilen sich denselben Zeitraum — wechselst du die Ansicht, bleibt der gewählte Zeitraum erhalten.

## Materialkostenquote

**Materialkostenquote = Materialkosten / Umsatz.** Die Materialkosten sind die verbrauchte Menge je Artikel multipliziert mit dem jeweils neuesten Wareneingangs-Preis (WE-Preis); der Umsatz ist der Netto-Umsatz (RG/GS). Niedriger ist besser.

Vier Kacheln:

- **Materialkostenquote** (%) — die Quote selbst, mit Delta-Badges gegenüber Vorperiode und Vorjahr, sobald ein Vergleichszeitraum vorliegt. Die Badges färben nach Vorzeichen der Veränderung.
- **Materialkosten** (€) — der Zähler.
- **Umsatz** (€) — der Nenner.
- **Ohne Preis** (Anzahl) — verbrauchte Artikel ohne WE-Preis. Sie fließen nicht in die Materialkosten ein und werden hier zur Transparenz ausgewiesen.

### Verlauf und einstellbare Ziellinie

Das Balkendiagramm zeigt die Materialkostenquote je Zeitabschnitt. Mit den Schaltflächen **−** / **+** oben rechts wechselst du die Granularität (Woche / Monat / Quartal / Jahr); über die Von-/Bis-Felder wählst du einen eigenen Zeitraum.

Ist in den Einstellungen ein Zielwert hinterlegt, erscheint eine gestrichelte **Ziellinie** (z. B. `Ziel 15,0 %`). Den Wert legst du unter **Einstellungen → Finanzen → Materialkostenquote** fest (in Prozent). Ein leeres Feld blendet die Linie aus.

### Prüftabelle „Materialverbrauch je Artikel"

Eine Zeile je verbrauchtem Artikel im Zeitraum. Spalten: Artikelnr, Bezeichnung, Verbrauchte Menge, Stückpreis (der verwendete WE-Preis) und Materialkosten. Die Tabelle ist durchsuchbar, über die Spaltenköpfe sortierbar und seitenweise blätterbar. Artikel ohne WE-Preis erscheinen gedämpft und mit „—" — sie zählen nicht zur Materialkosten-Summe.

## Personalkostenquote

**Personalkostenquote = Personalkosten / Umsatz.** Die Personalkosten sind die Brutto-Gehaltskosten aus Personio (Fixgehälter tagesgenau anteilig, Stundenlöhne über die erfassten Arbeitszeiten); der Umsatz ist derselbe Netto-Umsatz wie oben. Niedriger ist besser.

Vier Kacheln: **Personalkostenquote** (%, mit denselben Delta-Badges), **Personalkosten** (€, Zähler), **Umsatz** (€, Nenner) und **Mitarbeiter** (Anzahl der Mitarbeiter mit Kosten im Zeitraum).

Auch hier zeigt das Balkendiagramm den Verlauf mit Granularitäts-Schaltflächen und Von-/Bis-Feldern. Die Ziellinie legst du unter **Einstellungen → Finanzen → Personalkostenquote** fest.

Die Prüftabelle **Personalkosten je Abteilung** aggregiert je Abteilung — Spalten: Abteilung, Mitarbeiter, Personalkosten. Einzelgehälter werden nie angezeigt.

## Daten einspielen

Die Materialkostenquote speist sich aus hochgeladenen Exporten (Lagerbewegungen, Materialpreise/Wareneingang) und dem Umsatz; die Personalkostenquote nutzt die Personio-Daten (wie das HR-Dashboard) und ebenfalls den Umsatz. Eine Anleitung zum Hochladen findest du unter [Daten hochladen](/docs/user-guide/uploading-data). Zeitraumvoreinstellungen und eigene Zeiträume sind unter [Filter &amp; Zeiträume](/docs/user-guide/filters) erklärt.
