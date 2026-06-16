# WM 2026 — Tabelle, Spiele, KO & Torschützen als Signage-Views

**Datum:** 2026-06-16
**Status:** Entwurf (Design), wartet auf Implementierungsplan
**Baut auf:** [2026-06-11-worldcup-signage-design.md](2026-06-11-worldcup-signage-design.md)

## Ziel

Das bestehende World-Cup-Signage-Feature (heutige Live-Spiele mit Tor-Animation,
`/embed/worldcup`) um vier weitere Kiosk-Views erweitern, sodass auf einem Display
alles aus der FotMob-Übersicht gezeigt wird:

- **Übersicht** — heutige Spiele live *(existiert, nur minimale Anpassung)*
- **Tabelle** — die 12 Gruppentabellen
- **Spiele** — gestern / heute / morgen (Ergebnisse + kommende Anstöße)
- **KO-Spiele** — Achtelfinale → Finale
- **Torschützen** — Top-Scorer des Turniers

Jeder View ist eine eigene `/embed/...`-Seite, die der Admin in der bestehenden
Digital-Signage-Section als `url`-Medium in eine Playlist hängt. Die Rotation
zwischen den Views übernimmt der vorhandene Signage-Player; kein neuer
Signage-Code.

## Datenquelle

**football-data.org v4** (wie das bestehende Feature; FotMob hat keine nutzbare
API — als reine optische Vorlage akzeptiert, nicht als Quelle). Alle benötigten
Daten liegen im kostenlosen Tarif (Wettbewerb `WC`):

| View | Upstream |
|------|----------|
| Tabelle | `GET /v4/competitions/WC/standings` (Typ `GROUP`, 12 Gruppen) |
| Spiele | `GET /v4/competitions/WC/matches?dateFrom=<gestern>&dateTo=<morgen>` |
| KO-Spiele | `GET /v4/competitions/WC/matches` gefiltert auf KO-`stage` |
| Torschützen | `GET /v4/competitions/WC/scorers?limit=10` |

**Flaggen/Wappen:** football-data.org liefert pro Team eine `crest`-URL (die die
bestehende `MatchCard` schon nutzt). Diese wird in allen neuen Views neben dem
Teamnamen angezeigt. Bei fehlendem `crest` bleibt der Platz leer (kein Platzhalter-
Bild).

**Bewusst draußen (YAGNI):** Spielstatistik (Ballbesitz/Schüsse) und Tor-Events
pro Spiel mit Schützennamen — auf dem Gratis-Tarif nicht verfügbar, daher nicht
Teil dieses Designs. Daten bleiben Cache-only (nichts in PostgreSQL).

## Architektur

Gleiches Muster wie das bestehende Feature und die HR-Embeds: Backend-proxied
Feed mit Modul-Cache, public (kein Auth) Embed-Endpoint, Frontend-Embed-Seite,
die im Signage-Player als iframe läuft.

```
football-data.org   ←(1 Call pro Resource pro Intervall, server-seitig, Key geheim)
        │
backend/app/services/worldcup_feed.py   Modul-Cache pro Resource, TTL = refresh_seconds
        │
GET /api/worldcup/embed/{standings,matches,knockout,scorers}   public, JSON
        │
frontend /embed/worldcup/{standings,matches,knockout,scorers}  TanStack-Query-Polling
        │
Signage-Player iframe  (Playlist-Rotation, ?duration pro Element)
```

Eine Cache-Instanz pro Resource bedient beliebig viele Screens; Upstream wird
pro Resource höchstens einmal pro Intervall aufgerufen. Bei 4 zusätzlichen
Resources × ~1 Call/Minute bleibt das Gratis-Limit (10 Calls/Minute) klar
eingehalten.

## Backend

### Feed-Service (`backend/app/services/worldcup_feed.py`, erweitern)

Das bestehende `_Cache`/`get_feed`-Muster wird um drei weitere Resources ergänzt.
Bevorzugt eine generische Cache-Map `{resource_key → _Cache}` statt vier
copy-paste-Caches, damit `reset_cache()` (Tests) eine Stelle bleibt.

- `get_standings(api_key, refresh_seconds)` → Liste von Gruppen, je
  `{ group: "Group A", table: [{ position, team{name,short_name,crest}, played,
  won, draw, lost, goal_difference, points }] }`.
- `get_matches_window(api_key, refresh_seconds, tz_name)` → Spiele von **gestern
  bis morgen** (lokale Tagesgrenzen in `tz_name`, Default Europe/Berlin), gruppiert
  in `yesterday` / `today` / `tomorrow`; je Spiel das vorhandene `WorldCupMatch`-
  Schema (mit `crest`).
- `get_knockout(api_key, refresh_seconds)` → Spiele mit KO-`stage`
  (`LAST_16`/`QUARTER_FINALS`/`SEMI_FINALS`/`THIRD_PLACE`/`FINAL`; ggf.
  `LAST_32`, falls football-data.org das WM-Format so liefert), gruppiert nach
  Stage in fester Reihenfolge.
- `get_scorers(api_key, refresh_seconds)` → `[{ rank, player_name, team{name,
  short_name,crest}, goals }]` (max. 10).

Caching-Verhalten identisch zum bestehenden Feed: höchstens ein Upstream-Versuch
pro `refresh_seconds`; bei Upstream-Fehler die letzten guten Daten weiterliefern
und `stale_since` setzen; gab es nie einen Erfolg → `error`-Flag + leere Liste.
Kein `api_key` gesetzt → `error="not_configured"`.

### Router (`backend/app/routers/worldcup.py`, erweitern)

Vier neue **public** Endpoints (kein Auth), neben dem bestehenden
`GET /api/worldcup/embed/today`:

- `GET /api/worldcup/embed/standings`
- `GET /api/worldcup/embed/matches`
- `GET /api/worldcup/embed/knockout`
- `GET /api/worldcup/embed/scorers`

Jede Antwort enthält wie heute `refresh_seconds`, optional `stale_since`,
optional `error`. Der Modul-Docstring muss den public/admin-Split deklarieren
(Konvention „Auth gate placement"); `test_admin_gate_audit.py` muss grün bleiben,
und der OpenAPI-Snapshot (`backend/tests/contracts/openapi_paths.json`) wird um
die neuen Pfade ergänzt.

### Settings

**Unverändert.** API-Key (`worldcup.api_key`, geheim) und
`worldcup.refresh_seconds` werden von allen Views geteilt. **Keine** neue
Einstellung — die Anzeigedauer pro Screen bzw. pro Tabellen-Seite ist die
Element-Dauer der Signage-Playlist (siehe unten). Damit entfällt das ursprünglich
angedachte `worldcup_rotate_seconds`.

## Frontend — Embed-Seiten

Vier neue Seiten unter `frontend/src/pages/`, registriert in `App.tsx` neben den
übrigen `/embed/*`-Routen. Deutsch als Default, `?lang=en` als Override (Muster
von `EmbedJoinersPage`/`EmbedWorldCupPage`).

Gemeinsame Bausteine:
- Layout `h-screen w-screen overflow-hidden`, kein Scrollen.
- Polling per TanStack Query mit `refetchInterval` aus `refresh_seconds` der
  Antwort; `fetch` mit `credentials: "omit"` wie die anderen public Embed-Fetcher.
- Eine kleine wiederverwendbare `TeamFlag`-Komponente (crest-`<img>` mit
  Fallback) für alle Views; die bestehende `MatchCard` zeigt Flaggen bereits.
- Failure/Stale: niemals Fehlerseite; bei `stale_since` ein dezenter
  „Stand: HH:MM"-Hinweis.

### Signage-Lifetime-Vertrag (kritisch)

Der `PlayerRenderer` überspringt für `/embed/*`-URLs den äußeren Dauer-Timer
(`ownsOwnLifetime`); die Embed-Seite **muss** ihre Lebensdauer selbst beenden,
indem sie `window.parent.postMessage({ type: "embed-cycle-complete" }, "*")`
sendet — sonst bleibt der Screen in einer rotierenden Playlist hängen. Der Player
hängt `?duration=<Sekunden>` (= Element-Dauer) an die URL.

- **Tabelle** nutzt den bestehenden `useEmbedPaging(12, 6)`-Hook → 2 Seiten
  (Gruppen A–F, dann G–L), jede für `?duration` Sekunden; nach der letzten Seite
  feuert der Hook automatisch `embed-cycle-complete`. Wiederverwendung ohne
  Änderung.
- **Spiele / KO / Torschützen** sind in der Regel einseitig. Sie senden nach
  `?duration` Sekunden `embed-cycle-complete` (gleicher Mechanismus wie
  `useEmbedPaging` mit einer Seite). Läuft ein View doch über (z. B. ein Tag mit
  sehr vielen Spielen), paginiert `useEmbedPaging` mit passender `pageSize`.

### Anpassung der bestehenden Übersicht (`EmbedWorldCupPage`)

Heute sendet die Seite **kein** `embed-cycle-complete` und liest **kein**
`?duration` — sie funktioniert nur als Einzel-Element-Playlist. Damit sie in der
rotierenden 5er-Playlist mitläuft:

- Nach `?duration` Sekunden `embed-cycle-complete` senden.
- Das Signal **aufschieben, solange die Tor-Overlay-Queue nicht leer ist**, und
  erst nach Ende der laufenden Animation feuern — damit kein Tor mitten in der
  Animation weggeschaltet wird.

Standalone (direkt im Browser oder als Einzel-Element-Playlist) ist das
`postMessage` an `window.parent` ein harmloser No-op — bestehendes Verhalten
bleibt unverändert.

### Inhalte der Views

- **Tabelle** (`/embed/worldcup/standings`): Raster aus 6 Mini-Tabellen pro Seite
  (Gruppen A–F / G–L). Pro Gruppe: Position, Flagge + Teamname, Sp, Tordiff, Pkt.
- **Spiele** (`/embed/worldcup/matches`): drei Spalten „Gestern / Heute / Morgen".
  Gespielte Spiele mit Ergebnis, kommende mit Anstoßzeit, laufende mit Live-Badge.
  Leerer Tag → dezenter Hinweis statt leerer Spalte.
- **KO-Spiele** (`/embed/worldcup/knockout`): Spalten je Runde
  (Achtel → Viertel → Halb → Finale). Noch nicht ausgespielte Paarungen als
  „noch offen". Während der Gruppenphase (keine KO-Spiele) ein ruhiger
  „noch nicht entschieden"-Zustand.
- **Torschützen** (`/embed/worldcup/scorers`): die **Top 10** (Upstream
  `?limit=10`), als 2 Spalten à 5 Einträge — Rang, Flagge + Spielername,
  Toranzahl. Liefert der Upstream weniger (frühe Turnierphase), werden nur die
  vorhandenen gezeigt.

## Einbindung in die Digital-Signage-Section

Kein Code in `signage_admin`/`player`. Damit der Admin **nicht** fünf URLs von
Hand registrieren und eine Playlist zusammenbauen muss, wird eine fertige
**„WM 2026"-Playlist mitgeliefert** (Seed, siehe unten). Der Admin muss sie dann
nur noch einem Gerät zuweisen:

1. **Signage → Playlists**: Die Playlist „WM 2026" ist bereits vorhanden (alle 5
   Views in Reihenfolge, mit Standard-Dauern). Reihenfolge/Dauer bei Bedarf
   anpassen.
2. Der Playlist einen **Tag** geben (z. B. `lobby`); Geräte mit passendem Tag
   spielen sie sofort. (Tags sind geräteabhängig und werden daher nicht
   geseedet.)

Optional bleibt der manuelle Weg möglich (Signage → Medien → „URL registrieren"
+ eigene Playlist), falls jemand eine abweichende Zusammenstellung will.

### Vorbefüllte Playlist (Seed via Alembic-Datenmigration)

Eine neue Datenmigration (`backend/alembic/versions/v1_61_worldcup_playlist.py`)
legt idempotent an — mit **festen UUIDs** und `INSERT ... ON CONFLICT (id) DO
NOTHING`, sodass ein erneuter Lauf nichts dupliziert und ein vom Admin gelöschter
Eintrag nicht zurückkehrt:

- 5 `signage_media`-Zeilen (`kind='url'`):

  | Titel | uri |
  |-------|-----|
  | WM 2026 – Übersicht | `/embed/worldcup` |
  | WM 2026 – Tabelle | `/embed/worldcup/standings` |
  | WM 2026 – Spiele | `/embed/worldcup/matches` |
  | WM 2026 – KO-Runde | `/embed/worldcup/knockout` |
  | WM 2026 – Torschützen | `/embed/worldcup/scorers` |

- 1 `signage_playlists`-Zeile: `name='WM 2026'`, `enabled=true`.
- 5 `signage_playlist_items` (position 0–4, `transition='fade'`) mit
  Standard-Dauern als `duration_s` (Admin überschreibbar):

  | Position | View | duration_s |
  |----------|------|-----------|
  | 0 | Übersicht | 30 |
  | 1 | Tabelle | 15 *(pro 6er-Seite → ~30 s gesamt)* |
  | 2 | Spiele | 20 |
  | 3 | KO-Runde | 20 |
  | 4 | Torschützen | 20 |

Die `uri` sind **relative** Pfade (`/embed/...`), wie bei den bestehenden
HR-Embeds — der Player löst sie gegen den API-Host auf. **Keine** Tag-Zuordnung
im Seed (geräteabhängig).

Dokumentation: `frontend/src/docs/{de,en}/admin-guide/digital-signage.md` um einen
kurzen Abschnitt „WM-2026-Views" ergänzen (dass die fertige Playlist existiert,
nur noch ein Tag nötig ist, und dass Dauer = Zeit pro Screen bzw. pro
Tabellen-Seite bedeutet).

## Tests

- **Backend (mocked Upstream, keine Live-Calls):**
  - `standings`-Mapping (Gruppen + Tabellenzeilen, crest übernommen).
  - `matches`-Fenster: korrekte Gestern/Heute/Morgen-Einteilung über lokale
    Tagesgrenzen (`tz_name`), inkl. Mitternachtsfall.
  - `knockout`: Filterung auf KO-Stages + feste Stage-Reihenfolge.
  - `scorers`-Mapping inkl. Limit.
  - Cache-TTL (kein zweiter Upstream-Call innerhalb des Intervalls) und
    stale-on-failure pro Resource.
  - `test_admin_gate_audit.py` bleibt grün; OpenAPI-Snapshot um die 4 Pfade
    ergänzt.
  - Seed-Migration: nach Upgrade existieren Playlist „WM 2026" + 5 Items in
    korrekter Reihenfolge mit den 5 Embed-URLs; erneuter Lauf bzw.
    bereits-vorhandene IDs erzeugen keine Duplikate (ON CONFLICT DO NOTHING).
- **Frontend:**
  - `TeamFlag`-Fallback (kein crest → kein `<img>`).
  - Übersicht: `embed-cycle-complete` wird aufgeschoben, solange die
    Goal-Queue nicht leer ist, und danach genau einmal gefeuert.
  - Standings-Paging: `useEmbedPaging(12, 6)` → 2 Seiten (vorhandenes
    Hook-Verhalten, ggf. nur Abdeckung der neuen Nutzung).
- **Manuelle UAT:** Playlist mit allen 5 Views auf einem Gerät; ein voller
  Rotationsdurchlauf inkl. Tabellen-Seitenwechsel; an einem Spieltag eine
  Tor-Animation auf der Übersicht beobachten.

## Bewusst draußen

- Spielstatistik & Tor-Events pro Spiel (Tarif-Grenze football-data.org Gratis).
- Konfigurierbarer Wettbewerb (weiter hartkodiert `WC`).
- Interaktives Dashboard in der eingeloggten App (nur Kiosk-Embeds).
- Persistenz der Feed-Daten in PostgreSQL (Cache-only).
- Sound.
