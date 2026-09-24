# Produktions-Priorisierung

Stand: v1.126 (2026-09-15). Eigenständiges Modul unter **Produktion → Priorisierung**
(`/production/prio`, nur Admin). Alle Tabellen tragen das Präfix `prio_` und hängen an
keiner anderen Tabelle, damit sich das Modul später herauslösen lässt.

## Wozu

Aus den offenen Aufträgen, dem Apollo-Ressourcenplan und den Prioritätslisten der
Kunden entsteht eine **Gesamtpriorisierung** der BA-Positionen. Sie lässt sich per
Drag & Drop anpassen. Daraus werden je **Bereich** Tätigkeitslisten abgeleitet (Ansicht +
Excel-Export), heruntergebrochen über alle Stücklistenebenen.

## Datenquellen (Reiter „Import“)

| Quelle | Datei | Inhalt | Import |
|---|---|---|---|
| Auftragspositionen | `AswKpf.txt` (Apollo) | BA-Position, Artikel, Menge, Kunde, Lieferdatum, `St`, `Sperre manuell` | ersetzt `prio_auftrag_position` |
| Ressourcenplan | `dev_excel.txt` (Apollo RESSOURCENPLAN) | je Artikel einstufig: Halbzeug-/Artikel-Komponenten (mit Menge) und RES-Arbeitsgänge (Ressource, Kostenstelle, Rüst-/Operativzeit) | ersetzt `prio_plan_position`; Material/Werkzeug entfällt |
| Artikelstamm | `AswStm.txt` (Apollo) | Artikelbezeichnungen | ersetzt `prio_artikel` |
| Prioliste Diehl | `JJ-MM-TT_LoB_Auftragsbestand_Diehl_*.xlsx` | Blatt `Prioliste_Diehl` (Rang je MSN, ACM-Liefertermin, Kommentar) + Blatt `Auftragsbestand_ACM` (Code1 → Auftrag/Pos/UP) | neue Liste; Stand aus dem Dateinamen |

Die Apollo-Exporte enthalten Excel-Formelreste (`="…"`, v. a. Sitzvorlagen 0010xx), die die
Spaltenzahl sprengen. Diese Zeilen werden übersprungen und als Hinweis gemeldet. Diehl-Zeilen
ohne ACM-Auftrag („k. Auftrag“) werden ebenfalls übersprungen.

Der Arbeitsfolgenplan (`dev_excel_1.txt`) wird nicht importiert: Er ist die bereits
aufgelöste Form desselben Ressourcenplans (Zeiten zu 98–99 % identisch).

## Rechenregeln

**Gesamtliste** (`services/produktion_prio.py`)

Priorisiert wird auf **BA-Ebene** (BA = Auftrag/Vorgang aus AswKpf). Die Positionen des BA,
also die FAs der Fertigartikel samt ihrer Halbzeug-FAs, laufen mit.

1. Je Position gilt als Termin der Termin der gewinnenden Prioliste (Diehl: „ACM Liefertermin“),
   sonst das Lieferdatum aus AswKpf, dazu der Listenrang. Steht eine Position in mehreren
   Listen, gewinnt die Liste mit dem **jüngsten Stand**.
2. Ein BA sortiert nach seinem **frühesten Positionstermin**, dann nach dem **besten
   (kleinsten) Listenrang** seiner Positionen, dann nach BA-Nummer. BAs ohne Rang sortieren sich
   ebenfalls nach Termin.
3. Die **manuelle BA-Reihenfolge** (Drag & Drop oder Platz eintragen, dann „Reihenfolge speichern“)
   geht vor. Manuell sortierte BAs behalten untereinander ihre Reihenfolge und belegen die Plätze,
   die sie automatisch hätten. Neue BAs aus einem späteren Import landen an ihrem automatischen
   Platz. „Manuelle Sortierung zurücksetzen“ verwirft alles.
4. Innerhalb eines BA: Termin, Rang, Pos, UPos.

Positionen mit `Sperre manuell = J` bleiben in der Liste und sind als „gesperrt“ markiert.
„kein Ressourcenplan“ markiert Artikel ohne Eintrag im Ressourcenplan.

**Bereichslisten**

- Jede BA-Position wird über den Ressourcenplan rekursiv aufgelöst: Komponenten in
  Positionsreihenfolge, also Halbzeug vor dem Arbeitsgang, der es verbaut. Die Tiefe ist auf
  15 Ebenen begrenzt, Selbst- und Kreisbezüge werden übersprungen.
- Menge = Positionsmenge × Stücklistenmengen entlang des Pfads.
- Minuten = Rüstzeit + Operativzeit × Menge. Annahme: Minuten, Operativzeit je Stück.
- Jede Tätigkeit erbt den Platz ihres BA (Prio) sowie Termin, Sperre und Kommentar ihrer
  Position. Die Liste ist nach BA-Platz, Position und Arbeitsgangfolge sortiert.
  Halbzeuge haben keinen eigenen Vorlauf.

**Bereiche** (Zuordnung über die Ressourcennummer, `BEREICHE` im Service)

| Bereich | Ressourcen |
|---|---|
| Zuschnitt | 10000, 16000 |
| Näherei | 13000, 20000, 20002, 20003, 21000, 22000 |
| Bezieherei | 30000–30004 |
| Schäumerei | 31000, 31002, 31003 |
| Wandverkleidung | 40000, 41000, 48000 |
| Teppiche | 40001, 40002 |
| Spezialserie | 50000, 50001 |
| Gurte | 60000 |
| QS | 70000, 71000 |
| Verpackung | 80000, 81000 |
| Fremdvergabe | 1000, 1400, alle 1xx000 |
| Bemusterung | 90000, 90010 |
| Etikettendruck | 11000 |
| Sonstige | alles Übrige (z. B. 25000, 32000, 65000, 91000) |

Varianten wie `10000MA01` zählen zur Stammressource.

## API

Siehe Router-Docstring `backend/app/routers/produktion_prio.py`. Alle Routen liegen unter
`/api/production/prio` und sind admin-gated.

## Offen / nächste Schritte

- FA-Daten einhängen: erledigte Arbeitsgänge ausblenden (Ist-Stand z. B. aus `AswQs4443.txt`).
- Weitere Prioritätslisten-Formate (je Format ein Parser, `typ` in `prio_liste`).
- Die Bereichszuordnung ist aktuell Code; bei häufigen Änderungen in eine Tabelle überführen.
