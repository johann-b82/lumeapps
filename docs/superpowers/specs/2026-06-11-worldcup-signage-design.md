# World Cup Live Results — Signage Embed Page

**Date:** 2026-06-11
**Status:** Approved (design), pending implementation

## Goal

A kiosk/signage page showing today's FIFA World Cup 2026 matches in (near) real time,
with a full-screen animation whenever a goal is scored. Runs inside the existing
LumeApps signage player as an iframe, like the HR embed views. No scrolling — the
layout must fit any number of today's matches (0–6) on one 16:9 screen.

## Data source

**football-data.org v4** (decided; Google scraping rejected as ToS-violating and fragile).

- Endpoint: `GET https://api.football-data.org/v4/competitions/WC/matches?dateFrom=<today>&dateTo=<today>`
  with header `X-Auth-Token: <api key>`.
- Free tier covers the FIFA World Cup and allows 10 requests/minute — far above our
  one-call-per-interval usage.
- "Today" is computed in **Europe/Berlin** local time.
- Relevant fields: `homeTeam`/`awayTeam` (`name`, `shortName`, `crest`), `score.fullTime`
  (and `score.halfTime`), `status` (`SCHEDULED`/`TIMED`/`IN_PLAY`/`PAUSED`/`FINISHED`),
  `minute` (may be absent on the free tier — degrade to a plain "LIVE" badge), `utcDate`.

## Architecture

Backend-proxied feed, mirroring the existing HR embed pattern
(`backend/app/routers/hr_embed.py` + `/embed/*` frontend routes):

```
football-data.org  ←(1 call per interval, server-side, key secret)
        │
backend/app/routers/worldcup.py   in-memory cache, TTL = refresh interval
        │
GET /api/worldcup/embed/today     public (no auth), JSON
        │
frontend /embed/worldcup          TanStack Query polling at configured interval
        │
signage player iframe
```

One cache serves any number of screens; the upstream API is called at most once per
interval regardless of how many kiosks poll.

## Components

### Backend — `backend/app/routers/worldcup.py`

- `GET /api/worldcup/embed/today` — **public** (module docstring must declare the
  public/admin split per the auth-gate convention; `test_admin_gate_audit.py` guard
  applies). Response:
  ```json
  {
    "refreshSeconds": 60,
    "staleSince": null,
    "matches": [
      {
        "id": 12345,
        "home": {"name": "Deutschland", "shortName": "GER", "crest": "https://..."},
        "away": {"name": "Mexiko", "shortName": "MEX", "crest": "https://..."},
        "score": {"home": 1, "away": 0},
        "status": "IN_PLAY",
        "minute": 37,
        "kickoffUtc": "2026-06-11T19:00:00Z"
      }
    ],
    "nextMatchday": null
  }
  ```
- On rest days (`matches` empty), the response includes `nextMatchday`: the date and
  fixtures of the next day with World Cup matches (second upstream query, also cached).
- **Caching:** in-memory dict with timestamp; refetch upstream only when the cache is
  older than the configured refresh interval. On upstream failure, keep serving the
  last good payload and set `staleSince` to the timestamp of the last successful fetch.
  If there has never been a successful fetch, return `matches: []` with an `error` flag.
- **Settings** (stored via the existing settings system, admin-gated like other
  settings sections):
  - `worldcup.api_key` (string, secret — masked write-only input with a saved-hint,
    same pattern as the Personio client secret in `PersonioCard.tsx`)
  - `worldcup.refresh_seconds` (int, default 60, min 30 — protects the free-tier rate
    limit and the upstream service)

### Frontend — `/embed/worldcup`

New `frontend/src/pages/EmbedWorldCupPage.tsx`, registered in `App.tsx` next to the
other `/embed/*` routes. German UI default, `?lang=en` override (same pattern as
`EmbedJoinersPage`).

- **Layout:** `h-screen w-screen overflow-hidden`, no scrolling ever. Match cards in
  an auto-fit grid: 1 match → one large centered card; 2 → side by side; 3–4 → 2×2;
  5–6 → 2×3. Each card shows crests, team names, a large score, and a status badge
  (pulsing `LIVE 37'` / kickoff time `21:00` / `FT`).
- **Polling:** TanStack Query with `refetchInterval` taken from the response's
  `refreshSeconds`. Uses a plain `fetch` with `credentials: "omit"` like the other
  public embed fetchers in `frontend/src/lib/api.ts`.
- **Goal animation:** the page keeps the previous poll's scores (by match id). When a
  team's goal count increases, a full-screen overlay fires for ~6 seconds: "⚽ TOR!"
  (or "GOAL!" in English), the scoring team's crest and name, and the new score, with
  CSS keyframe animation (scale/flash — no new dependencies). Multiple simultaneous
  goals queue and play sequentially. On the very first poll after page load there is
  no previous state, so no animation fires (prevents replaying old goals on restart).
- **Empty state:** "Heute keine Spiele" plus the next matchday's fixtures from
  `nextMatchday`.
- **Failure state:** keep rendering the last data; if the response carries
  `staleSince`, show a small unobtrusive "Stand: HH:MM" hint. Never an error page on
  a signage screen.

### Settings UI

A "World Cup" card (API key + refresh interval) added to the existing Settings page,
following the `SalesTargetsCard` / `PersonioCard` pattern and the
`SettingsSectionPicker` registration. i18n strings in `de.json`/`en.json`.

## Out of scope

- Other competitions / configurable competition code (hardcoded `WC`).
- Group tables, knockout brackets, match statistics.
- Sound on goal animation.
- Persisting match data in PostgreSQL — the feed is ephemeral, cache-only.

## Testing

- **Backend:** unit tests for the upstream-payload → response mapping, cache TTL
  behaviour (no second upstream call within the interval), stale-on-failure handling,
  and rest-day `nextMatchday`. Upstream is mocked — no live API calls in tests.
  `test_admin_gate_audit.py` must stay green with the new public endpoint declared.
- **Frontend:** unit tests for the goal-detection diff (score increase → animation
  event; first poll → no event; decrease/correction → no event).
- **Manual UAT:** point the signage player at `/embed/worldcup` during a live match
  day and observe a refresh cycle and a goal overlay.
