# WM 2026 — internes Tippspiel (Abteilungs-Rangliste)

**Date:** 2026-06-22
**Status:** Approved (design), implementation in progress

## Goal

5 Abteilungen tippen die WM-2026-Spiele (Tipps in einer Excel-Datei). Das
System liest die Tipps ein, vergleicht sie täglich mit den echten
Ergebnissen (Live-Feed), berechnet Punkte und zeigt eine Rangliste auf den
Signage-Displays.

## Punkteregel (pro Spiel & Abteilung)

Echtes Ergebnis ist ein **Sieg** (es gibt einen Sieger):
- exaktes Ergebnis → **5**
- richtiger Sieger **und** richtige Tordifferenz (nicht exakt) → **3**
- nur richtiger Sieger (Tendenz) → **2**
- falsche Tendenz → **0**

Echtes Ergebnis ist ein **Unentschieden**:
- exaktes Ergebnis → **5**
- Unentschieden getippt (aber nicht exakt) → **3**
- kein Unentschieden getippt → **0**

(Für Unentschieden gibt es keine separate Tordifferenz-Stufe — ein getipptes
Unentschieden hat zwangsläufig die richtige Tordifferenz 0.)

## Datenquelle der Ergebnisse

Der vorhandene WM-Feed (`worldcup_feed.py`) holt von **football-data.org**
`/competitions/{WC}/matches` **alle** Spiele inkl. `status` und
`score.fullTime`. `_fetch_all_matches` liefert die komplette Liste; daraus
filtern wir `status == "FINISHED"`. „Täglich" ergibt sich aus dem
Feed-Refresh-Intervall — kein separater Cron.

## Excel-Struktur (Quelle)

Blatt **„WM 2026 Tipps"**, Spalten:
`Gruppe | Datum | Spiel | Büro-Admin/Hamburg | Wandverkleidung | Schaum/Montage
| Näherei/Teppich | ACM-Team/Memmingen | Ergebnis | Punkte`.
- Gruppen-Kopfzeilen (`Gruppe A` …) ohne Spiel → überspringen.
- Match-Zeilen: `Spiel` = „Heim – Gast" (dt. Namen). Je Abteilung ein Tipp
  „H:A".
- **Excel-Zeit-Artefakt:** manche Tipps wurden zu Zeiten konvertiert
  (`datetime.time(3,0)` = Tipp „3:0", `time(0,3)` = „0:3"). Beim Parsen
  `time(h,m) → "h:m"` zurückrechnen.
- `Ergebnis`/`Punkte` sind leer (werden nicht gelesen).

## Architektur

### Backend

1. **Team-Mapping** `app/services/tippspiel_teams.py`: dict dt. Name →
   football-data-Name (Mexiko→Mexico, Südafrika→South Africa, Südkorea→South
   Korea, Tschechien→Czechia, Bosnien-Herzegowina→Bosnia and Herzegovina …).
   Aus den tatsächlich in der Excel vorkommenden Namen gepflegt; ein Test
   stellt sicher, dass **jeder** Excel-Name gemappt ist.
2. **Parser** `app/parsing/tippspiel_parser.py`:
   `parse_tippspiel_file(contents) -> (rows, errors, departments)`. Eine
   Zeile pro (Spiel, Abteilung): `{gruppe, home, away, match_date,
   department, tip_home, tip_away, raw}`. Heim/Gast über das Mapping auf
   football-data-Namen normalisiert.
3. **Tabelle** `tippspiel_tips` + Migration `v1_61`: `home_team`,
   `away_team`, `match_date`, `department`, `tip_home`, `tip_away`,
   `upload_batch_id`, `raw`. Upsert-Key `(home_team, away_team, department)`.
   `upload_batches.kind` um `tippspiel` erweitert.
4. **Upload** (Admin) `POST /api/upload-tippspiel` (xlsx, Composite-Upsert) —
   spiegelt die bestehenden Upload-Endpoints.
5. **Scoring** `app/services/tippspiel_scoring.py` (rein, testbar):
   `score_tip(tip, result) -> int` (die Regel oben) und
   `compute_ranking(tips, finished_matches) -> list[DeptRow]`. Matching der
   Tipps an die FINISHED-Matches über (home, away) mit Reverse-Fallback
   (Orientierung anhand des Feeds). „Punkte letzte Spiele" = Summe der Punkte
   aus den Spielen des **jüngsten** ausgewerteten Datums.
6. **Endpoint** `GET /api/worldcup/embed/tippspiel` (public, wie die anderen
   WM-Embeds): lädt Feed (gecacht) + Tipps, gibt
   `[{rank, department, last_points, total_points}]` sortiert nach
   `total_points` desc zurück.

### Frontend

7. **Embed-Seite** `pages/EmbedWorldCupTippspielPage.tsx` + Route
   `/embed/worldcup/tippspiel`: Signage-große Tabelle **Platzierung |
   Abteilung | Punkte letzte Spiele | Gesamtpunkte**, `useEmbedPaging`
   (sendet `embed-cycle-complete`), Stil wie die anderen WM-Seiten. API-Client
   + i18n-Strings.

### Anzeige / Playlist

8. Neues `kind='url'`-Medium (absolute Caddy-URL
   `http://192.9.200.178/embed/worldcup/tippspiel`) als 6. Item in die
   „WM 2026"-Playlist (DB) — nach dem Arash-Muster.

## Error handling

- Parser: fehlende/leere Tipps → Zeile übersprungen (kein harter Fehler);
  unbekannter Teamname → Error-Eintrag (Mapping-Lücke sichtbar).
- Scoring: Spiele ohne FINISHED-Match (noch nicht gespielt) zählen nicht.
- Endpoint: kein Feed/keine Tipps → leere Rangliste, nie 500.

## Testing

- **Parser** (kein DB): Beispielzeilen inkl. Zeit-Artefakt, Gruppen-Kopf
  übersprungen, fehlende Tipps.
- **Mapping**: jeder Excel-Teamname ist gemappt (Vollständigkeit).
- **Scoring** (rein): alle Fälle — exakt, Sieg-Tordifferenz, Sieg-Tendenz,
  Unentschieden-getippt, falsch; + Reverse-Orientierung.
- **Endpoint**: Ranking-Reihenfolge + last/total auf Fixtures (acm_kpi_test).
- **Embed**: rendert + paginiert (postet `embed-cycle-complete`).

## Non-goals

- Kein separater Cron (Live-Feed deckt „täglich" ab).
- Keine Knockout-Tipps (Excel = Gruppenphase; spätere Spiele kommen über
  denselben Mechanismus, sobald Tipps vorliegen).
