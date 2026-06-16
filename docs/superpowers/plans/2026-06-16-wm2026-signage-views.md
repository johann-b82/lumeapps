# WM 2026 Signage Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four kiosk embed views (group standings, matches gestern/heute/morgen, knockout bracket, top scorers) to the existing World Cup signage feature, plus a ready-made "WM 2026" playlist seeded via migration.

**Architecture:** Mirror the existing `/embed/worldcup` feature exactly: football-data.org is proxied server-side in `services/worldcup_feed.py` with a per-resource module cache (TTL = `refresh_seconds`, stale-on-failure); four new public endpoints in `routers/worldcup.py`; four new unauthenticated `/embed/worldcup/*` React pages that honor the signage player lifetime contract (`?duration` + `postMessage("embed-cycle-complete")`). An Alembic data migration seeds the media rows + playlist.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, httpx, Pydantic v2, Alembic; React 19 + TypeScript, TanStack Query, Tailwind, react-i18next, Vitest, pytest.

**Spec:** [docs/superpowers/specs/2026-06-16-wm2026-signage-views-design.md](../specs/2026-06-16-wm2026-signage-views-design.md)

---

## File Structure

**Backend**
- Modify `backend/app/services/worldcup_feed.py` — add generic per-resource cache + standings/matches-window/knockout/scorers models, mappers, and `get_*` services.
- Modify `backend/app/routers/worldcup.py` — add 4 public endpoints.
- Create `backend/alembic/versions/v1_61_worldcup_playlist.py` — seed media + playlist.
- Modify `backend/tests/test_admin_gate_audit.py` — allowlist 4 new public paths.
- Modify `backend/tests/contracts/openapi_paths.json` — add 4 new paths.
- Create `backend/tests/test_worldcup_extra_feeds.py` — unit tests for new mappers/services.
- Modify `backend/tests/test_worldcup_embed.py` — endpoint tests for the 4 routes.
- Create `backend/tests/test_worldcup_playlist_seed.py` — migration seed test.

**Frontend**
- Modify `frontend/src/lib/api.ts` — types + fetchers for the 4 feeds.
- Create `frontend/src/components/worldcup/TeamFlag.tsx` — crest image with fallback.
- Create `frontend/src/pages/EmbedWorldCupStandingsPage.tsx`
- Create `frontend/src/pages/EmbedWorldCupMatchesPage.tsx`
- Create `frontend/src/pages/EmbedWorldCupKnockoutPage.tsx`
- Create `frontend/src/pages/EmbedWorldCupScorersPage.tsx`
- Modify `frontend/src/App.tsx` — register 4 routes.
- Modify `frontend/src/pages/EmbedWorldCupPage.tsx` — post `embed-cycle-complete` (deferred during goal overlay).
- Modify `frontend/src/locales/de.json` + `frontend/src/locales/en.json` — new i18n keys.
- Create `frontend/src/pages/EmbedWorldCupPage.test.tsx` — cycle-complete deferral test.
- Create `frontend/src/components/worldcup/TeamFlag.test.tsx` — fallback test.
- Modify `frontend/src/docs/de/admin-guide/digital-signage.md` + `.../en/...` — document the ready-made playlist.

**football-data.org response shapes (reference for mappers)**

Standings: `GET /v4/competitions/WC/standings` →
```json
{ "standings": [
  { "stage": "GROUP_STAGE", "type": "TOTAL", "group": "GROUP_A",
    "table": [ { "position": 1,
      "team": {"name":"Mexico","shortName":"Mexico","tla":"MEX","crest":"https://..."},
      "playedGames": 3, "won": 3, "draw": 0, "lost": 0,
      "points": 9, "goalsFor": 7, "goalsAgainst": 2, "goalDifference": 5 } ] } ] }
```
Matches: `GET /v4/competitions/WC/matches[?dateFrom&dateTo]` → `{ "matches": [ { "id", "utcDate", "status", "minute", "stage": "GROUP_STAGE"|"LAST_16"|..., "group", "homeTeam":{...}, "awayTeam":{...}, "score": {"fullTime": {"home","away"}} } ] }`
Scorers: `GET /v4/competitions/WC/scorers?limit=10` → `{ "scorers": [ { "player": {"name":"Kylian Mbappé"}, "team": {"name","shortName","tla","crest"}, "goals": 6 } ] }`

---

## Task 1: Standings model, mapper, and cached service

**Files:**
- Modify: `backend/app/services/worldcup_feed.py`
- Test: `backend/tests/test_worldcup_extra_feeds.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_worldcup_extra_feeds.py`:

```python
"""Unit tests for the extra World Cup feeds (standings, matches window,
knockout, scorers) — no DB, no network. Upstream fetchers and the clock are
monkeypatched on module globals; reset_cache() isolates tests."""
from datetime import date, datetime, timezone

import httpx
import pytest

from app.services import worldcup_feed as wcf


@pytest.fixture(autouse=True)
def fresh_cache():
    wcf.reset_cache()
    yield
    wcf.reset_cache()


def _raw_group(group="GROUP_A", tla="MEX"):
    return {
        "stage": "GROUP_STAGE",
        "type": "TOTAL",
        "group": group,
        "table": [
            {
                "position": 1,
                "team": {"name": "Mexico", "shortName": "Mexico", "tla": tla,
                         "crest": "https://crests.football-data.org/mex.png"},
                "playedGames": 3, "won": 3, "draw": 0, "lost": 0,
                "points": 9, "goalsFor": 7, "goalsAgainst": 2, "goalDifference": 5,
            }
        ],
    }


def test_build_standings_maps_groups_and_skips_non_total():
    raw = [_raw_group(), {"type": "HOME", "group": "GROUP_A", "table": []}]
    feed = wcf.build_standings(raw, 60)
    assert [g.group for g in feed.groups] == ["Group A"]
    row = feed.groups[0].table[0]
    assert row.position == 1
    assert row.team.name == "Mexico"
    assert row.team.crest.endswith("mex.png")
    assert (row.played, row.won, row.draw, row.lost) == (3, 3, 0, 0)
    assert row.goal_difference == 5
    assert row.points == 9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_worldcup_extra_feeds.py::test_build_standings_maps_groups_and_skips_non_total -v`
Expected: FAIL with `AttributeError: module 'app.services.worldcup_feed' has no attribute 'build_standings'`.

- [ ] **Step 3: Add the standings model, mapper, generic cache, fetcher, and service**

In `backend/app/services/worldcup_feed.py`, add the imports `field`-free Pydantic models and helpers. After the existing `WorldCupFeed` model add:

```python
class StandingsRow(BaseModel):
    position: int
    team: WorldCupTeam
    played: int
    won: int
    draw: int
    lost: int
    goal_difference: int
    points: int


class StandingsGroup(BaseModel):
    group: str
    table: list[StandingsRow] = []


class StandingsFeed(BaseModel):
    refresh_seconds: int
    stale_since: datetime | None = None
    error: str | None = None
    groups: list[StandingsGroup] = []
```

Add a generic per-resource cache registry next to the existing `_cache`:

```python
# Extra feeds (standings/matches/knockout/scorers) each get their own cache
# entry so one upstream call per resource per interval serves every kiosk.
_caches: dict[str, _Cache] = {}
```

Extend `reset_cache()` to also clear the registry:

```python
def reset_cache() -> None:
    global _cache
    _cache = _Cache()
    _caches.clear()
```

Add the generic cached-raw helper:

```python
async def _cached_raw(key: str, refresh_seconds: int, fetch):
    """Return (raw, stale_since) for `key`, fetching at most once per interval.
    `fetch` is a zero-arg async callable returning the upstream payload.
    On failure the last good raw is kept and stale_since is set."""
    now = _utcnow()
    cache = _caches.setdefault(key, _Cache())
    async with cache.lock:
        due = (
            cache.attempted_at is None
            or (now - cache.attempted_at).total_seconds() >= refresh_seconds
        )
        if due:
            cache.attempted_at = now
            try:
                cache.raw = await fetch()
                cache.fetched_at = now
            except (httpx.HTTPError, ValueError):
                pass
        stale = None
        if (
            cache.fetched_at is not None
            and cache.attempted_at is not None
            and cache.fetched_at < cache.attempted_at
        ):
            stale = cache.fetched_at
        return cache.raw, stale
```

Add the standings fetcher, mapper, and service:

```python
def _group_label(raw_group: str | None) -> str:
    # "GROUP_A" -> "Group A"; pass through anything unexpected.
    if not raw_group:
        return "?"
    return raw_group.replace("_", " ").title()


def build_standings(raw: list[dict[str, Any]], refresh_seconds: int) -> StandingsFeed:
    groups: list[StandingsGroup] = []
    for block in raw:
        if block.get("type") != "TOTAL":
            continue
        rows = [
            StandingsRow(
                position=r["position"],
                team=WorldCupTeam(
                    name=(r.get("team") or {}).get("name") or "?",
                    short_name=(r.get("team") or {}).get("shortName")
                    or (r.get("team") or {}).get("tla"),
                    crest=(r.get("team") or {}).get("crest"),
                ),
                played=r.get("playedGames") or 0,
                won=r.get("won") or 0,
                draw=r.get("draw") or 0,
                lost=r.get("lost") or 0,
                goal_difference=r.get("goalDifference") or 0,
                points=r.get("points") or 0,
            )
            for r in block.get("table", [])
        ]
        groups.append(StandingsGroup(group=_group_label(block.get("group")), table=rows))
    return StandingsFeed(refresh_seconds=refresh_seconds, groups=groups)


async def _fetch_standings(api_key: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{FOOTBALL_DATA_BASE}/competitions/{COMPETITION_CODE}/standings",
            headers={"X-Auth-Token": api_key},
        )
        resp.raise_for_status()
        return resp.json().get("standings", [])


async def get_standings(api_key: str, refresh_seconds: int) -> StandingsFeed:
    raw, stale = await _cached_raw(
        "standings", refresh_seconds, lambda: _fetch_standings(api_key)
    )
    if raw is None:
        return StandingsFeed(refresh_seconds=refresh_seconds, error="upstream_unavailable")
    feed = build_standings(raw, refresh_seconds)
    feed.stale_since = stale
    return feed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_worldcup_extra_feeds.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/worldcup_feed.py backend/tests/test_worldcup_extra_feeds.py
git commit -m "feat(worldcup): standings feed (groups, cached, stale-on-failure)"
```

---

## Task 2: Matches-window model, mapper, and cached service

**Files:**
- Modify: `backend/app/services/worldcup_feed.py`
- Test: `backend/tests/test_worldcup_extra_feeds.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_worldcup_extra_feeds.py`:

```python
def _raw_match(id, utc, status="FINISHED", home=2, away=1, stage="GROUP_STAGE"):
    return {
        "id": id, "utcDate": utc, "status": status, "minute": None, "stage": stage,
        "homeTeam": {"name": "A", "shortName": "A", "tla": "AAA", "crest": None},
        "awayTeam": {"name": "B", "shortName": "B", "tla": "BBB", "crest": None},
        "score": {"fullTime": {"home": home, "away": away}},
    }


def test_build_matches_window_splits_by_local_day():
    raws = [
        _raw_match(1, "2026-06-10T15:00:00Z"),   # yesterday
        _raw_match(2, "2026-06-11T19:00:00Z", status="IN_PLAY"),  # today
        _raw_match(3, "2026-06-12T15:00:00Z", status="TIMED"),    # tomorrow
        _raw_match(4, "2026-06-09T15:00:00Z"),   # out of window -> dropped
    ]
    feed = wcf.build_matches_window(raws, "Europe/Berlin", date(2026, 6, 11), 60)
    assert [m.id for m in feed.yesterday] == [1]
    assert [m.id for m in feed.today] == [2]
    assert [m.id for m in feed.tomorrow] == [3]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_worldcup_extra_feeds.py::test_build_matches_window_splits_by_local_day -v`
Expected: FAIL with `AttributeError: ... has no attribute 'build_matches_window'`.

- [ ] **Step 3: Add the matches-window model and service**

In `worldcup_feed.py`, add after `StandingsFeed`:

```python
class MatchesWindowFeed(BaseModel):
    refresh_seconds: int
    stale_since: datetime | None = None
    error: str | None = None
    yesterday: list[WorldCupMatch] = []
    today: list[WorldCupMatch] = []
    tomorrow: list[WorldCupMatch] = []
```

Add the builder and service (reuses the existing `_fetch_upstream` and `map_match`):

```python
def build_matches_window(
    raw_matches: list[dict[str, Any]], tz_name: str, today: date, refresh_seconds: int
) -> MatchesWindowFeed:
    tz = ZoneInfo(tz_name)
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    buckets: dict[date, list[WorldCupMatch]] = {yesterday: [], today: [], tomorrow: []}
    for raw in raw_matches:
        m = map_match(raw)
        local_day = m.kickoff_utc.astimezone(tz).date()
        if local_day in buckets:
            buckets[local_day].append(m)
    for v in buckets.values():
        v.sort(key=lambda m: m.kickoff_utc)
    return MatchesWindowFeed(
        refresh_seconds=refresh_seconds,
        yesterday=buckets[yesterday],
        today=buckets[today],
        tomorrow=buckets[tomorrow],
    )


async def get_matches_window(
    api_key: str, refresh_seconds: int, tz_name: str
) -> MatchesWindowFeed:
    now = _utcnow()
    today = now.astimezone(ZoneInfo(tz_name)).date()
    raw, stale = await _cached_raw(
        "matches_window",
        refresh_seconds,
        lambda: _fetch_upstream(api_key, today - timedelta(days=1), today + timedelta(days=1)),
    )
    if raw is None:
        return MatchesWindowFeed(refresh_seconds=refresh_seconds, error="upstream_unavailable")
    feed = build_matches_window(raw, tz_name, today, refresh_seconds)
    feed.stale_since = stale
    return feed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_worldcup_extra_feeds.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/worldcup_feed.py backend/tests/test_worldcup_extra_feeds.py
git commit -m "feat(worldcup): matches-window feed (yesterday/today/tomorrow)"
```

---

## Task 3: Knockout model, mapper, and cached service

**Files:**
- Modify: `backend/app/services/worldcup_feed.py`
- Test: `backend/tests/test_worldcup_extra_feeds.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_worldcup_extra_feeds.py`:

```python
def test_build_knockout_filters_and_orders_stages():
    raws = [
        _raw_match(1, "2026-07-05T19:00:00Z", stage="FINAL"),
        _raw_match(2, "2026-07-01T19:00:00Z", stage="LAST_16"),
        _raw_match(3, "2026-06-20T19:00:00Z", stage="GROUP_STAGE"),  # dropped
    ]
    feed = wcf.build_knockout(raws, 60)
    assert [s.stage for s in feed.stages] == ["LAST_16", "FINAL"]
    assert [m.id for m in feed.stages[0].matches] == [2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_worldcup_extra_feeds.py::test_build_knockout_filters_and_orders_stages -v`
Expected: FAIL with `AttributeError: ... has no attribute 'build_knockout'`.

- [ ] **Step 3: Add the knockout model, fetcher, and service**

In `worldcup_feed.py`, add after `MatchesWindowFeed`:

```python
# Knockout stages in display order. LAST_32 included for the 48-team format;
# absent stages simply produce no group.
KNOCKOUT_STAGES = [
    "LAST_32",
    "LAST_16",
    "QUARTER_FINALS",
    "SEMI_FINALS",
    "THIRD_PLACE",
    "FINAL",
]


class KnockoutStage(BaseModel):
    stage: str
    matches: list[WorldCupMatch] = []


class KnockoutFeed(BaseModel):
    refresh_seconds: int
    stale_since: datetime | None = None
    error: str | None = None
    stages: list[KnockoutStage] = []
```

Add the builder, fetcher, and service:

```python
def build_knockout(raw_matches: list[dict[str, Any]], refresh_seconds: int) -> KnockoutFeed:
    by_stage: dict[str, list[WorldCupMatch]] = {}
    for raw in raw_matches:
        stage = raw.get("stage")
        if stage in KNOCKOUT_STAGES:
            by_stage.setdefault(stage, []).append(map_match(raw))
    stages = [
        KnockoutStage(stage=s, matches=sorted(by_stage[s], key=lambda m: m.kickoff_utc))
        for s in KNOCKOUT_STAGES
        if s in by_stage
    ]
    return KnockoutFeed(refresh_seconds=refresh_seconds, stages=stages)


async def _fetch_all_matches(api_key: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{FOOTBALL_DATA_BASE}/competitions/{COMPETITION_CODE}/matches",
            headers={"X-Auth-Token": api_key},
        )
        resp.raise_for_status()
        return resp.json().get("matches", [])


async def get_knockout(api_key: str, refresh_seconds: int) -> KnockoutFeed:
    raw, stale = await _cached_raw(
        "knockout", refresh_seconds, lambda: _fetch_all_matches(api_key)
    )
    if raw is None:
        return KnockoutFeed(refresh_seconds=refresh_seconds, error="upstream_unavailable")
    feed = build_knockout(raw, refresh_seconds)
    feed.stale_since = stale
    return feed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_worldcup_extra_feeds.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/worldcup_feed.py backend/tests/test_worldcup_extra_feeds.py
git commit -m "feat(worldcup): knockout feed (stage-filtered, ordered)"
```

---

## Task 4: Scorers model, mapper, and cached service

**Files:**
- Modify: `backend/app/services/worldcup_feed.py`
- Test: `backend/tests/test_worldcup_extra_feeds.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_worldcup_extra_feeds.py`:

```python
def test_build_scorers_ranks_and_maps():
    raw = [
        {"player": {"name": "Kylian Mbappé"},
         "team": {"name": "France", "shortName": "France", "tla": "FRA",
                  "crest": "https://crests.football-data.org/fra.png"},
         "goals": 6},
        {"player": {"name": "Harry Kane"},
         "team": {"name": "England", "shortName": "England", "tla": "ENG", "crest": None},
         "goals": 4},
    ]
    feed = wcf.build_scorers(raw, 60)
    assert [s.rank for s in feed.scorers] == [1, 2]
    assert feed.scorers[0].player_name == "Kylian Mbappé"
    assert feed.scorers[0].team.name == "France"
    assert feed.scorers[0].goals == 6


@pytest.mark.asyncio
async def test_get_scorers_caches_within_ttl(monkeypatch):
    calls = []

    async def fake(api_key):
        calls.append(1)
        return [{"player": {"name": "X"}, "team": {"name": "Y"}, "goals": 1}]

    monkeypatch.setattr(wcf, "_fetch_scorers", fake)
    monkeypatch.setattr(wcf, "_utcnow", lambda: datetime(2026, 6, 11, 12, tzinfo=timezone.utc))
    await wcf.get_scorers("k", 60)
    await wcf.get_scorers("k", 60)
    assert len(calls) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_worldcup_extra_feeds.py::test_build_scorers_ranks_and_maps -v`
Expected: FAIL with `AttributeError: ... has no attribute 'build_scorers'`.

- [ ] **Step 3: Add the scorers model, fetcher, and service**

In `worldcup_feed.py`, add after `KnockoutFeed`:

```python
SCORERS_LIMIT = 10


class ScorerRow(BaseModel):
    rank: int
    player_name: str
    team: WorldCupTeam
    goals: int


class ScorersFeed(BaseModel):
    refresh_seconds: int
    stale_since: datetime | None = None
    error: str | None = None
    scorers: list[ScorerRow] = []
```

Add the builder, fetcher, and service:

```python
def build_scorers(raw: list[dict[str, Any]], refresh_seconds: int) -> ScorersFeed:
    rows = [
        ScorerRow(
            rank=i + 1,
            player_name=(s.get("player") or {}).get("name") or "?",
            team=WorldCupTeam(
                name=(s.get("team") or {}).get("name") or "?",
                short_name=(s.get("team") or {}).get("shortName")
                or (s.get("team") or {}).get("tla"),
                crest=(s.get("team") or {}).get("crest"),
            ),
            goals=s.get("goals") or 0,
        )
        for i, s in enumerate(raw)
    ]
    return ScorersFeed(refresh_seconds=refresh_seconds, scorers=rows)


async def _fetch_scorers(api_key: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{FOOTBALL_DATA_BASE}/competitions/{COMPETITION_CODE}/scorers",
            params={"limit": SCORERS_LIMIT},
            headers={"X-Auth-Token": api_key},
        )
        resp.raise_for_status()
        return resp.json().get("scorers", [])


async def get_scorers(api_key: str, refresh_seconds: int) -> ScorersFeed:
    raw, stale = await _cached_raw(
        "scorers", refresh_seconds, lambda: _fetch_scorers(api_key)
    )
    if raw is None:
        return ScorersFeed(refresh_seconds=refresh_seconds, error="upstream_unavailable")
    feed = build_scorers(raw, refresh_seconds)
    feed.stale_since = stale
    return feed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_worldcup_extra_feeds.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/worldcup_feed.py backend/tests/test_worldcup_extra_feeds.py
git commit -m "feat(worldcup): scorers feed (top 10, ranked)"
```

---

## Task 5: Four public router endpoints + guards

**Files:**
- Modify: `backend/app/routers/worldcup.py`
- Modify: `backend/tests/test_admin_gate_audit.py:63`
- Modify: `backend/tests/contracts/openapi_paths.json:70`
- Test: `backend/tests/test_worldcup_embed.py`

- [ ] **Step 1: Write the failing endpoint tests**

Append to `backend/tests/test_worldcup_embed.py`:

```python
@pytest.mark.asyncio
async def test_standings_endpoint_unauthenticated(client, monkeypatch):
    await _set_worldcup(encrypt_credential("test-key"))

    async def fake(api_key):
        return [{"type": "TOTAL", "group": "GROUP_A", "table": [
            {"position": 1,
             "team": {"name": "Mexico", "shortName": "Mexico", "tla": "MEX", "crest": None},
             "playedGames": 3, "won": 3, "draw": 0, "lost": 0,
             "points": 9, "goalsFor": 7, "goalsAgainst": 2, "goalDifference": 5}]}]

    monkeypatch.setattr(wcf, "_fetch_standings", fake)
    r = await client.get("/api/worldcup/embed/standings")
    assert r.status_code == 200
    assert r.json()["groups"][0]["group"] == "Group A"


@pytest.mark.asyncio
async def test_matches_endpoint_not_configured(client):
    await _set_worldcup(None)
    r = await client.get("/api/worldcup/embed/matches")
    assert r.status_code == 200
    assert r.json()["error"] == "not_configured"


@pytest.mark.asyncio
async def test_knockout_and_scorers_endpoints(client, monkeypatch):
    await _set_worldcup(encrypt_credential("test-key"))

    async def fake_matches(api_key):
        return [{"id": 1, "utcDate": "2026-07-05T19:00:00Z", "status": "TIMED",
                 "stage": "FINAL", "minute": None,
                 "homeTeam": {"name": "A", "tla": "AAA", "crest": None},
                 "awayTeam": {"name": "B", "tla": "BBB", "crest": None},
                 "score": {"fullTime": {"home": None, "away": None}}}]

    async def fake_scorers(api_key):
        return [{"player": {"name": "X"}, "team": {"name": "Y"}, "goals": 3}]

    monkeypatch.setattr(wcf, "_fetch_all_matches", fake_matches)
    monkeypatch.setattr(wcf, "_fetch_scorers", fake_scorers)
    rk = await client.get("/api/worldcup/embed/knockout")
    rs = await client.get("/api/worldcup/embed/scorers")
    assert rk.json()["stages"][0]["stage"] == "FINAL"
    assert rs.json()["scorers"][0]["rank"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_worldcup_embed.py -k "standings or matches or knockout" -v`
Expected: FAIL with 404 (routes not registered).

- [ ] **Step 3: Add the four endpoints**

In `backend/app/routers/worldcup.py`, update the imports and add the routes. Replace the import line:

```python
from app.services.worldcup_feed import (
    KnockoutFeed,
    MatchesWindowFeed,
    ScorersFeed,
    StandingsFeed,
    WorldCupFeed,
    get_feed,
    get_knockout,
    get_matches_window,
    get_scorers,
    get_standings,
)
```

Add a small helper and the four routes below `embed_today`:

```python
async def _settings(db: AsyncSession):
    row = (
        await db.execute(select(AppSettings).where(AppSettings.id == 1))
    ).scalar_one_or_none()
    refresh = row.worldcup_refresh_seconds if row is not None else 60
    api_key = (
        decrypt_credential(row.worldcup_api_key_enc)
        if row is not None and row.worldcup_api_key_enc
        else None
    )
    tz = row.timezone if row is not None else "Europe/Berlin"
    return api_key, refresh, tz


@router.get("/embed/standings", response_model=StandingsFeed)
async def embed_standings(db: AsyncSession = Depends(get_async_db_session)) -> StandingsFeed:
    api_key, refresh, _ = await _settings(db)
    if api_key is None:
        return StandingsFeed(refresh_seconds=refresh, error="not_configured")
    return await get_standings(api_key, refresh)


@router.get("/embed/matches", response_model=MatchesWindowFeed)
async def embed_matches(db: AsyncSession = Depends(get_async_db_session)) -> MatchesWindowFeed:
    api_key, refresh, tz = await _settings(db)
    if api_key is None:
        return MatchesWindowFeed(refresh_seconds=refresh, error="not_configured")
    return await get_matches_window(api_key, refresh, tz)


@router.get("/embed/knockout", response_model=KnockoutFeed)
async def embed_knockout(db: AsyncSession = Depends(get_async_db_session)) -> KnockoutFeed:
    api_key, refresh, _ = await _settings(db)
    if api_key is None:
        return KnockoutFeed(refresh_seconds=refresh, error="not_configured")
    return await get_knockout(api_key, refresh)


@router.get("/embed/scorers", response_model=ScorersFeed)
async def embed_scorers(db: AsyncSession = Depends(get_async_db_session)) -> ScorersFeed:
    api_key, refresh, _ = await _settings(db)
    if api_key is None:
        return ScorersFeed(refresh_seconds=refresh, error="not_configured")
    return await get_scorers(api_key, refresh)
```

- [ ] **Step 4: Update the admin-gate allowlist**

In `backend/tests/test_admin_gate_audit.py`, after the existing `("/api/worldcup/embed/today", frozenset({"GET"})),` line (63) add:

```python
    ("/api/worldcup/embed/standings", frozenset({"GET"})),
    ("/api/worldcup/embed/matches", frozenset({"GET"})),
    ("/api/worldcup/embed/knockout", frozenset({"GET"})),
    ("/api/worldcup/embed/scorers", frozenset({"GET"})),
```

- [ ] **Step 5: Update the OpenAPI path snapshot**

In `backend/tests/contracts/openapi_paths.json`, immediately before the `"/api/worldcup/embed/today",` entry (line 70), insert the four new paths in sorted order:

```json
  "/api/worldcup/embed/knockout",
  "/api/worldcup/embed/matches",
  "/api/worldcup/embed/scorers",
  "/api/worldcup/embed/standings",
```

- [ ] **Step 6: Run the full backend guard + endpoint suite**

Run: `cd backend && python -m pytest tests/test_worldcup_embed.py tests/test_admin_gate_audit.py tests/test_openapi_paths_snapshot.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/worldcup.py backend/tests/test_worldcup_embed.py backend/tests/test_admin_gate_audit.py backend/tests/contracts/openapi_paths.json
git commit -m "feat(worldcup): public standings/matches/knockout/scorers endpoints"
```

---

## Task 6: Seed migration for the ready-made "WM 2026" playlist

**Files:**
- Create: `backend/alembic/versions/v1_61_worldcup_playlist.py`
- Test: `backend/tests/test_worldcup_playlist_seed.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_worldcup_playlist_seed.py`:

```python
"""The v1_61 seed creates a ready-made 'WM 2026' playlist with 5 url media
items in order. Verifies presence + ordering against the live (migrated) DB."""
import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import SignageMedia, SignagePlaylist, SignagePlaylistItem


@pytest.mark.asyncio
async def test_wm2026_playlist_seeded():
    async with AsyncSessionLocal() as s:
        pl = (
            await s.execute(select(SignagePlaylist).where(SignagePlaylist.name == "WM 2026"))
        ).scalar_one_or_none()
        assert pl is not None, "WM 2026 playlist must be seeded by v1_61"
        items = (
            await s.execute(
                select(SignagePlaylistItem)
                .where(SignagePlaylistItem.playlist_id == pl.id)
                .order_by(SignagePlaylistItem.position)
            )
        ).scalars().all()
        assert len(items) == 5
        uris = []
        for it in items:
            media = (
                await s.execute(select(SignageMedia).where(SignageMedia.id == it.media_id))
            ).scalar_one()
            assert media.kind == "url"
            uris.append(media.uri)
        assert uris == [
            "/embed/worldcup",
            "/embed/worldcup/standings",
            "/embed/worldcup/matches",
            "/embed/worldcup/knockout",
            "/embed/worldcup/scorers",
        ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_worldcup_playlist_seed.py -v`
Expected: FAIL with `AssertionError: WM 2026 playlist must be seeded by v1_61`.

- [ ] **Step 3: Write the migration**

Create `backend/alembic/versions/v1_61_worldcup_playlist.py`. Uses fixed UUIDs + `ON CONFLICT (id) DO NOTHING` for idempotency:

```python
"""v1.61: seed ready-made 'WM 2026' signage playlist

Creates 5 url media rows (the worldcup embed views), one playlist, and 5
playlist items in order. Fixed UUIDs + ON CONFLICT DO NOTHING make a re-run a
no-op and avoid resurrecting an admin-deleted row. No tag map — tags are
device-specific and assigned by the admin.
"""
from alembic import op

revision = "v1_61_worldcup_playlist"
down_revision = "v1_60_procurement_otd"
branch_labels = None
depends_on = None

PLAYLIST_ID = "11111111-1111-4111-8111-111111111111"
VIEWS = [
    ("22222222-2222-4222-8222-222222222201", "WM 2026 – Übersicht", "/embed/worldcup", 30),
    ("22222222-2222-4222-8222-222222222202", "WM 2026 – Tabelle", "/embed/worldcup/standings", 15),
    ("22222222-2222-4222-8222-222222222203", "WM 2026 – Spiele", "/embed/worldcup/matches", 20),
    ("22222222-2222-4222-8222-222222222204", "WM 2026 – KO-Runde", "/embed/worldcup/knockout", 20),
    ("22222222-2222-4222-8222-222222222205", "WM 2026 – Torschützen", "/embed/worldcup/scorers", 20),
]
ITEM_IDS = [
    "33333333-3333-4333-8333-333333333301",
    "33333333-3333-4333-8333-333333333302",
    "33333333-3333-4333-8333-333333333303",
    "33333333-3333-4333-8333-333333333304",
    "33333333-3333-4333-8333-333333333305",
]


def upgrade() -> None:
    conn = op.get_bind()
    for media_id, title, uri, _ in VIEWS:
        conn.exec_driver_sql(
            "INSERT INTO signage_media (id, kind, title, uri) "
            "VALUES (%s, 'url', %s, %s) ON CONFLICT (id) DO NOTHING",
            (media_id, title, uri),
        )
    conn.exec_driver_sql(
        "INSERT INTO signage_playlists (id, name, enabled) "
        "VALUES (%s, 'WM 2026', true) ON CONFLICT (id) DO NOTHING",
        (PLAYLIST_ID,),
    )
    for position, ((media_id, _t, _u, duration), item_id) in enumerate(zip(VIEWS, ITEM_IDS)):
        conn.exec_driver_sql(
            "INSERT INTO signage_playlist_items "
            "(id, playlist_id, media_id, position, duration_s, transition) "
            "VALUES (%s, %s, %s, %s, %s, 'fade') ON CONFLICT (id) DO NOTHING",
            (item_id, PLAYLIST_ID, media_id, position, duration),
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql(
        "DELETE FROM signage_playlist_items WHERE playlist_id = %s", (PLAYLIST_ID,)
    )
    conn.exec_driver_sql("DELETE FROM signage_playlists WHERE id = %s", (PLAYLIST_ID,))
    for media_id, _t, _u, _d in VIEWS:
        conn.exec_driver_sql("DELETE FROM signage_media WHERE id = %s", (media_id,))
```

> Note: the test DB must be at head for this test. If the suite builds the schema via `alembic upgrade head` in a fixture, no extra step is needed. If it uses `Base.metadata.create_all`, run `cd backend && python -m alembic upgrade head` against the test DB before this test, or add an autouse fixture that executes the migration's `upgrade()`. Confirm which by checking `backend/tests/conftest.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m alembic upgrade head && python -m pytest tests/test_worldcup_playlist_seed.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/v1_61_worldcup_playlist.py backend/tests/test_worldcup_playlist_seed.py
git commit -m "feat(worldcup): seed ready-made 'WM 2026' signage playlist"
```

---

## Task 7: Frontend types + fetchers

**Files:**
- Modify: `frontend/src/lib/api.ts:499`

- [ ] **Step 1: Add types and fetchers**

In `frontend/src/lib/api.ts`, after `fetchWorldCupTodayPublic` (line 499) add:

```typescript
export interface StandingsRow {
  position: number;
  team: WorldCupTeam;
  played: number;
  won: number;
  draw: number;
  lost: number;
  goal_difference: number;
  points: number;
}
export interface StandingsGroup {
  group: string;
  table: StandingsRow[];
}
export interface StandingsFeed {
  refresh_seconds: number;
  stale_since: string | null;
  error: string | null;
  groups: StandingsGroup[];
}
export interface MatchesWindowFeed {
  refresh_seconds: number;
  stale_since: string | null;
  error: string | null;
  yesterday: WorldCupMatch[];
  today: WorldCupMatch[];
  tomorrow: WorldCupMatch[];
}
export interface KnockoutStage {
  stage: string;
  matches: WorldCupMatch[];
}
export interface KnockoutFeed {
  refresh_seconds: number;
  stale_since: string | null;
  error: string | null;
  stages: KnockoutStage[];
}
export interface ScorerRow {
  rank: number;
  player_name: string;
  team: WorldCupTeam;
  goals: number;
}
export interface ScorersFeed {
  refresh_seconds: number;
  stale_since: string | null;
  error: string | null;
  scorers: ScorerRow[];
}

async function fetchWorldCupPublic<T>(path: string): Promise<T> {
  const r = await fetch(path, { credentials: "omit" });
  if (!r.ok) throw new Error(`worldcup embed fetch failed: ${r.status}`);
  return (await r.json()) as T;
}
export const fetchWorldCupStandingsPublic = () =>
  fetchWorldCupPublic<StandingsFeed>("/api/worldcup/embed/standings");
export const fetchWorldCupMatchesPublic = () =>
  fetchWorldCupPublic<MatchesWindowFeed>("/api/worldcup/embed/matches");
export const fetchWorldCupKnockoutPublic = () =>
  fetchWorldCupPublic<KnockoutFeed>("/api/worldcup/embed/knockout");
export const fetchWorldCupScorersPublic = () =>
  fetchWorldCupPublic<ScorersFeed>("/api/worldcup/embed/scorers");
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no type errors).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(worldcup): frontend types + fetchers for new embed feeds"
```

---

## Task 8: TeamFlag component

**Files:**
- Create: `frontend/src/components/worldcup/TeamFlag.tsx`
- Test: `frontend/src/components/worldcup/TeamFlag.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/worldcup/TeamFlag.test.tsx`:

```typescript
import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TeamFlag } from "./TeamFlag";

describe("TeamFlag", () => {
  it("renders an img when a crest is present", () => {
    const { container } = render(
      <TeamFlag team={{ name: "France", short_name: "FRA", crest: "https://x/fra.png" }} />,
    );
    expect(container.querySelector("img")).not.toBeNull();
  });

  it("renders no img when crest is null", () => {
    const { container } = render(
      <TeamFlag team={{ name: "France", short_name: "FRA", crest: null }} />,
    );
    expect(container.querySelector("img")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/worldcup/TeamFlag.test.tsx`
Expected: FAIL (cannot resolve `./TeamFlag`).

- [ ] **Step 3: Write the component**

Create `frontend/src/components/worldcup/TeamFlag.tsx`:

```typescript
import type { WorldCupTeam } from "@/lib/api";

/** Country flag/crest from football-data.org. Empty box when no crest so
 *  layout stays stable (no broken-image icon on the signage screen). */
export function TeamFlag({ team, className = "h-5 w-7" }: { team: WorldCupTeam; className?: string }) {
  if (!team.crest) return <div className={`${className} shrink-0`} aria-hidden="true" />;
  return <img src={team.crest} alt="" className={`${className} object-contain shrink-0`} />;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/worldcup/TeamFlag.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/worldcup/TeamFlag.tsx frontend/src/components/worldcup/TeamFlag.test.tsx
git commit -m "feat(worldcup): TeamFlag component with crest fallback"
```

---

## Task 9: Standings embed page + route

**Files:**
- Create: `frontend/src/pages/EmbedWorldCupStandingsPage.tsx`
- Modify: `frontend/src/App.tsx:11,124`

- [ ] **Step 1: Write the page**

Create `frontend/src/pages/EmbedWorldCupStandingsPage.tsx`:

```typescript
/**
 * EmbedWorldCupStandingsPage — kiosk /embed/worldcup/standings.
 * Shows the 12 group tables 6-per-page via useEmbedPaging; the player drives
 * per-page time with ?duration and advances on embed-cycle-complete.
 */
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { fetchWorldCupStandingsPublic, type StandingsFeed } from "@/lib/api";
import { TeamFlag } from "@/components/worldcup/TeamFlag";
import { useEmbedPaging } from "@/components/dashboard/useEmbedPaging";

const PAGE_SIZE = 6;

export function EmbedWorldCupStandingsPage() {
  const { t, i18n } = useTranslation();
  useEffect(() => {
    const lang = new URLSearchParams(window.location.search).get("lang") ?? "de";
    if (i18n.language !== lang) void i18n.changeLanguage(lang);
  }, [i18n]);

  const { data } = useQuery<StandingsFeed>({
    queryKey: ["worldcup", "embed-standings"],
    queryFn: fetchWorldCupStandingsPublic,
    refetchInterval: (q) => Math.max(30, q.state.data?.refresh_seconds ?? 60) * 1000,
    refetchIntervalInBackground: true,
  });

  const groups = data?.groups ?? [];
  const { page } = useEmbedPaging(Math.max(groups.length, 1), PAGE_SIZE);
  const shown = groups.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  return (
    <div className="h-screen w-screen overflow-hidden bg-background flex flex-col p-6 gap-4">
      <h1 className="text-3xl font-bold shrink-0">{t("worldcup.standings_title")}</h1>
      <div className="grid flex-1 min-h-0 grid-cols-3 grid-rows-2 gap-4">
        {shown.map((g) => (
          <div key={g.group} className="rounded-2xl border-2 border-border bg-card p-3 flex flex-col min-h-0">
            <div className="text-xl font-semibold mb-2">{g.group}</div>
            <table className="w-full text-lg tabular-nums">
              <tbody>
                {g.table.map((r) => (
                  <tr key={r.position} className="border-b border-border/50 last:border-0">
                    <td className="py-1 pr-2 text-muted-foreground">{r.position}</td>
                    <td className="py-1 pr-2"><TeamFlag team={r.team} className="h-4 w-6 inline-block" /></td>
                    <td className="py-1 truncate">{r.team.name}</td>
                    <td className="py-1 px-1 text-center text-muted-foreground">{r.played}</td>
                    <td className="py-1 px-1 text-center text-muted-foreground">{r.goal_difference > 0 ? `+${r.goal_difference}` : r.goal_difference}</td>
                    <td className="py-1 pl-1 text-right font-semibold">{r.points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Register the route**

In `frontend/src/App.tsx`, add the import after line 11:

```typescript
import { EmbedWorldCupStandingsPage } from "./pages/EmbedWorldCupStandingsPage";
```

And add the route after line 124 (`<Route path="/embed/worldcup" .../>`):

```tsx
      <Route path="/embed/worldcup/standings" component={EmbedWorldCupStandingsPage} />
```

> Routing note: `wouter`'s `<Switch>` matches in order; place the more specific `/embed/worldcup/standings` route AFTER `/embed/worldcup` only if `/embed/worldcup` is an exact match (it is — wouter routes are exact by default). Verify the standings URL renders the standings page, not the today page, in Step 3.

- [ ] **Step 3: Verify in the preview**

Run the dev server (preview_start) and load `/embed/worldcup/standings?duration=15`. Confirm: a 3×2 grid of group cards renders (or an empty grid before data), no console errors, no scrollbars. (Data will be empty unless an API key is configured — layout is what we verify here.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/EmbedWorldCupStandingsPage.tsx frontend/src/App.tsx
git commit -m "feat(worldcup): standings embed page (/embed/worldcup/standings)"
```

---

## Task 10: Matches embed page + route

**Files:**
- Create: `frontend/src/pages/EmbedWorldCupMatchesPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the page**

Create `frontend/src/pages/EmbedWorldCupMatchesPage.tsx`:

```typescript
/**
 * EmbedWorldCupMatchesPage — kiosk /embed/worldcup/matches.
 * Three columns: gestern / heute / morgen. Single page; useEmbedPaging(1,1)
 * posts embed-cycle-complete after ?duration so the player advances.
 */
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  fetchWorldCupMatchesPublic,
  type MatchesWindowFeed,
  type WorldCupMatch,
} from "@/lib/api";
import { TeamFlag } from "@/components/worldcup/TeamFlag";
import { useEmbedPaging } from "@/components/dashboard/useEmbedPaging";

function MatchRow({ m }: { m: WorldCupMatch }) {
  const { i18n } = useTranslation();
  const started = m.status !== "SCHEDULED" && m.status !== "TIMED";
  const live = m.status === "IN_PLAY" || m.status === "PAUSED";
  const right = started
    ? `${m.score_home ?? 0}:${m.score_away ?? 0}`
    : new Date(m.kickoff_utc).toLocaleTimeString(i18n.language, { hour: "2-digit", minute: "2-digit" });
  return (
    <div className="flex items-center justify-between gap-2 py-2 border-b border-border/50 last:border-0 text-xl">
      <span className="flex items-center gap-2 min-w-0">
        <TeamFlag team={m.home} className="h-4 w-6" />
        <span className="truncate">{m.home.short_name ?? m.home.name}</span>
        <span className="text-muted-foreground">–</span>
        <TeamFlag team={m.away} className="h-4 w-6" />
        <span className="truncate">{m.away.short_name ?? m.away.name}</span>
      </span>
      <span className={`font-semibold tabular-nums ${live ? "text-destructive animate-pulse" : ""}`}>{right}</span>
    </div>
  );
}

function Column({ title, matches }: { title: string; matches: WorldCupMatch[] }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-2xl border-2 border-border bg-card p-4 flex flex-col min-h-0 overflow-hidden">
      <div className="text-2xl font-semibold mb-2 shrink-0">{title}</div>
      {matches.length > 0 ? (
        <div className="flex-1 min-h-0">{matches.map((m) => <MatchRow key={m.id} m={m} />)}</div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-muted-foreground">{t("worldcup.no_matches")}</div>
      )}
    </div>
  );
}

export function EmbedWorldCupMatchesPage() {
  const { t, i18n } = useTranslation();
  useEffect(() => {
    const lang = new URLSearchParams(window.location.search).get("lang") ?? "de";
    if (i18n.language !== lang) void i18n.changeLanguage(lang);
  }, [i18n]);

  const { data } = useQuery<MatchesWindowFeed>({
    queryKey: ["worldcup", "embed-matches"],
    queryFn: fetchWorldCupMatchesPublic,
    refetchInterval: (q) => Math.max(30, q.state.data?.refresh_seconds ?? 60) * 1000,
    refetchIntervalInBackground: true,
  });
  useEmbedPaging(1, 1); // single page → posts embed-cycle-complete after ?duration

  return (
    <div className="h-screen w-screen overflow-hidden bg-background flex flex-col p-6 gap-4">
      <h1 className="text-3xl font-bold shrink-0">{t("worldcup.matches_title")}</h1>
      <div className="grid flex-1 min-h-0 grid-cols-3 gap-4">
        <Column title={t("worldcup.yesterday")} matches={data?.yesterday ?? []} />
        <Column title={t("worldcup.today")} matches={data?.today ?? []} />
        <Column title={t("worldcup.tomorrow")} matches={data?.tomorrow ?? []} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Register the route**

In `frontend/src/App.tsx` add the import next to the other embed imports:

```typescript
import { EmbedWorldCupMatchesPage } from "./pages/EmbedWorldCupMatchesPage";
```

And the route next to the standings route:

```tsx
      <Route path="/embed/worldcup/matches" component={EmbedWorldCupMatchesPage} />
```

- [ ] **Step 3: Verify in the preview**

Load `/embed/worldcup/matches?duration=20`. Confirm three columns render with empty-state text, no console errors, no scrollbars.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/EmbedWorldCupMatchesPage.tsx frontend/src/App.tsx
git commit -m "feat(worldcup): matches embed page (gestern/heute/morgen)"
```

---

## Task 11: Knockout embed page + route

**Files:**
- Create: `frontend/src/pages/EmbedWorldCupKnockoutPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the page**

Create `frontend/src/pages/EmbedWorldCupKnockoutPage.tsx`:

```typescript
/**
 * EmbedWorldCupKnockoutPage — kiosk /embed/worldcup/knockout.
 * One column per knockout stage. Single page; useEmbedPaging(1,1) drives
 * the lifetime. Empty (group stage) → calm "noch nicht entschieden".
 */
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  fetchWorldCupKnockoutPublic,
  type KnockoutFeed,
  type WorldCupMatch,
} from "@/lib/api";
import { TeamFlag } from "@/components/worldcup/TeamFlag";
import { useEmbedPaging } from "@/components/dashboard/useEmbedPaging";

const STAGE_KEY: Record<string, string> = {
  LAST_32: "worldcup.stage.last_32",
  LAST_16: "worldcup.stage.last_16",
  QUARTER_FINALS: "worldcup.stage.quarter",
  SEMI_FINALS: "worldcup.stage.semi",
  THIRD_PLACE: "worldcup.stage.third",
  FINAL: "worldcup.stage.final",
};

function Pairing({ m }: { m: WorldCupMatch }) {
  const { i18n } = useTranslation();
  const started = m.status !== "SCHEDULED" && m.status !== "TIMED";
  const right = started
    ? `${m.score_home ?? 0}:${m.score_away ?? 0}`
    : new Date(m.kickoff_utc).toLocaleString(i18n.language, { weekday: "short", hour: "2-digit", minute: "2-digit" });
  return (
    <div className="flex items-center justify-between gap-2 py-2 border-b border-border/50 last:border-0 text-lg">
      <span className="flex items-center gap-1 min-w-0">
        <TeamFlag team={m.home} className="h-4 w-6" /><span className="truncate">{m.home.short_name ?? m.home.name}</span>
        <span className="text-muted-foreground">–</span>
        <TeamFlag team={m.away} className="h-4 w-6" /><span className="truncate">{m.away.short_name ?? m.away.name}</span>
      </span>
      <span className="font-semibold tabular-nums whitespace-nowrap">{right}</span>
    </div>
  );
}

export function EmbedWorldCupKnockoutPage() {
  const { t, i18n } = useTranslation();
  useEffect(() => {
    const lang = new URLSearchParams(window.location.search).get("lang") ?? "de";
    if (i18n.language !== lang) void i18n.changeLanguage(lang);
  }, [i18n]);

  const { data } = useQuery<KnockoutFeed>({
    queryKey: ["worldcup", "embed-knockout"],
    queryFn: fetchWorldCupKnockoutPublic,
    refetchInterval: (q) => Math.max(30, q.state.data?.refresh_seconds ?? 60) * 1000,
    refetchIntervalInBackground: true,
  });
  useEmbedPaging(1, 1);

  const stages = data?.stages ?? [];

  return (
    <div className="h-screen w-screen overflow-hidden bg-background flex flex-col p-6 gap-4">
      <h1 className="text-3xl font-bold shrink-0">{t("worldcup.knockout_title")}</h1>
      {stages.length > 0 ? (
        <div className="grid flex-1 min-h-0 gap-4" style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(0, 1fr))` }}>
          {stages.map((s) => (
            <div key={s.stage} className="rounded-2xl border-2 border-border bg-card p-4 flex flex-col min-h-0 overflow-hidden">
              <div className="text-xl font-semibold mb-2 shrink-0">{t(STAGE_KEY[s.stage] ?? s.stage)}</div>
              <div className="flex-1 min-h-0">{s.matches.map((m) => <Pairing key={m.id} m={m} />)}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-4xl text-muted-foreground">
          {t("worldcup.knockout_pending")}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Register the route**

In `frontend/src/App.tsx`:

```typescript
import { EmbedWorldCupKnockoutPage } from "./pages/EmbedWorldCupKnockoutPage";
```
```tsx
      <Route path="/embed/worldcup/knockout" component={EmbedWorldCupKnockoutPage} />
```

- [ ] **Step 3: Verify in the preview**

Load `/embed/worldcup/knockout?duration=20`. With no data, confirm the "noch nicht entschieden" empty state renders centered, no console errors, no scrollbars.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/EmbedWorldCupKnockoutPage.tsx frontend/src/App.tsx
git commit -m "feat(worldcup): knockout embed page (/embed/worldcup/knockout)"
```

---

## Task 12: Scorers embed page + route

**Files:**
- Create: `frontend/src/pages/EmbedWorldCupScorersPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the page**

Create `frontend/src/pages/EmbedWorldCupScorersPage.tsx`:

```typescript
/**
 * EmbedWorldCupScorersPage — kiosk /embed/worldcup/scorers.
 * Top 10 in two columns of 5. Single page; useEmbedPaging(1,1) drives lifetime.
 */
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { fetchWorldCupScorersPublic, type ScorersFeed } from "@/lib/api";
import { TeamFlag } from "@/components/worldcup/TeamFlag";
import { useEmbedPaging } from "@/components/dashboard/useEmbedPaging";

export function EmbedWorldCupScorersPage() {
  const { t, i18n } = useTranslation();
  useEffect(() => {
    const lang = new URLSearchParams(window.location.search).get("lang") ?? "de";
    if (i18n.language !== lang) void i18n.changeLanguage(lang);
  }, [i18n]);

  const { data } = useQuery<ScorersFeed>({
    queryKey: ["worldcup", "embed-scorers"],
    queryFn: fetchWorldCupScorersPublic,
    refetchInterval: (q) => Math.max(30, q.state.data?.refresh_seconds ?? 60) * 1000,
    refetchIntervalInBackground: true,
  });
  useEmbedPaging(1, 1);

  const scorers = data?.scorers ?? [];

  return (
    <div className="h-screen w-screen overflow-hidden bg-background flex flex-col p-6 gap-4">
      <h1 className="text-3xl font-bold shrink-0">{t("worldcup.scorers_title")}</h1>
      <div className="grid flex-1 min-h-0 grid-cols-2 gap-x-12 gap-y-1 content-start text-2xl">
        {scorers.map((s) => (
          <div key={s.rank} className="flex items-center gap-3 py-2 border-b border-border/50">
            <span className="text-muted-foreground w-8 tabular-nums">{s.rank}.</span>
            <TeamFlag team={s.team} className="h-5 w-7" />
            <span className="truncate flex-1">{s.player_name}</span>
            <span className="font-bold tabular-nums">{s.goals}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Register the route**

In `frontend/src/App.tsx`:

```typescript
import { EmbedWorldCupScorersPage } from "./pages/EmbedWorldCupScorersPage";
```
```tsx
      <Route path="/embed/worldcup/scorers" component={EmbedWorldCupScorersPage} />
```

- [ ] **Step 3: Verify in the preview**

Load `/embed/worldcup/scorers?duration=20`. Confirm a two-column layout renders (empty without data), no console errors, no scrollbars.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/EmbedWorldCupScorersPage.tsx frontend/src/App.tsx
git commit -m "feat(worldcup): scorers embed page (/embed/worldcup/scorers)"
```

---

## Task 13: Make the live Übersicht advance in a rotating playlist

**Files:**
- Modify: `frontend/src/pages/EmbedWorldCupPage.tsx`
- Test: `frontend/src/pages/EmbedWorldCupPage.test.tsx`

The existing page never posts `embed-cycle-complete`, so it hangs in a multi-item playlist (the player skips the outer timer for `/embed/*` URLs — see `PlayerRenderer.ownsOwnLifetime`). Add a cycle timer that fires after `?duration`, deferred while the goal-overlay queue is non-empty.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/EmbedWorldCupPage.test.tsx`:

```typescript
import { render } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { detectGoals } from "@/components/worldcup/goalDetection";
import { shouldPostCycle } from "./EmbedWorldCupPage";

describe("worldcup overview cycle gating", () => {
  it("defers the cycle while a goal overlay is queued", () => {
    expect(shouldPostCycle(true, 1)).toBe(false);  // timer elapsed, goal queued
    expect(shouldPostCycle(true, 0)).toBe(true);    // timer elapsed, queue empty
    expect(shouldPostCycle(false, 0)).toBe(false);  // timer not elapsed
  });

  it("re-exports detectGoals unchanged (sanity import)", () => {
    expect(typeof detectGoals).toBe("function");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/EmbedWorldCupPage.test.tsx`
Expected: FAIL (`shouldPostCycle` not exported).

- [ ] **Step 3: Add the gating helper + cycle effect**

In `frontend/src/pages/EmbedWorldCupPage.tsx`:

Add the pure helper near the top (after `GOAL_OVERLAY_MS`):

```typescript
const DEFAULT_CYCLE_S = 30;

/** Post embed-cycle-complete only once the display time has elapsed AND no
 *  goal overlay is currently queued (so we never cut a goal animation off). */
export function shouldPostCycle(timerElapsed: boolean, goalQueueLength: number): boolean {
  return timerElapsed && goalQueueLength === 0;
}
```

Inside `EmbedWorldCupPage`, after the existing goal-queue effects, add:

```typescript
  const [timerElapsed, setTimerElapsed] = useState(false);
  const postedRef = useRef(false);
  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get("duration");
    const parsed = raw != null ? parseInt(raw, 10) : NaN;
    const seconds = Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_CYCLE_S;
    const id = window.setTimeout(() => setTimerElapsed(true), seconds * 1000);
    return () => window.clearTimeout(id);
  }, []);
  useEffect(() => {
    if (postedRef.current) return;
    if (shouldPostCycle(timerElapsed, goalQueue.length)) {
      postedRef.current = true;
      try {
        window.parent.postMessage({ type: "embed-cycle-complete" }, "*");
      } catch {
        /* cross-origin post can throw — harmless when standalone */
      }
    }
  }, [timerElapsed, goalQueue.length]);
```

Ensure `useState` and `useRef` are imported (they already are: `import { useEffect, useRef, useState } from "react";`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/EmbedWorldCupPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/EmbedWorldCupPage.tsx frontend/src/pages/EmbedWorldCupPage.test.tsx
git commit -m "feat(worldcup): overview posts embed-cycle-complete (deferred during goal)"
```

---

## Task 14: i18n keys (de + en)

**Files:**
- Modify: `frontend/src/locales/de.json:539`
- Modify: `frontend/src/locales/en.json` (matching `worldcup.*` block)

- [ ] **Step 1: Add German keys**

In `frontend/src/locales/de.json`, after `"worldcup.not_configured"` (line 539) add:

```json
  "worldcup.standings_title": "WM Tabelle",
  "worldcup.matches_title": "WM Spiele",
  "worldcup.knockout_title": "WM K.-o.-Runde",
  "worldcup.scorers_title": "WM Torschützen",
  "worldcup.yesterday": "Gestern",
  "worldcup.today": "Heute",
  "worldcup.tomorrow": "Morgen",
  "worldcup.knockout_pending": "Noch nicht entschieden",
  "worldcup.stage.last_32": "Sechzehntelfinale",
  "worldcup.stage.last_16": "Achtelfinale",
  "worldcup.stage.quarter": "Viertelfinale",
  "worldcup.stage.semi": "Halbfinale",
  "worldcup.stage.third": "Spiel um Platz 3",
  "worldcup.stage.final": "Finale",
```

- [ ] **Step 2: Add English keys**

In `frontend/src/locales/en.json`, in the matching `worldcup.*` block add:

```json
  "worldcup.standings_title": "World Cup Standings",
  "worldcup.matches_title": "World Cup Matches",
  "worldcup.knockout_title": "World Cup Knockout",
  "worldcup.scorers_title": "World Cup Top Scorers",
  "worldcup.yesterday": "Yesterday",
  "worldcup.today": "Today",
  "worldcup.tomorrow": "Tomorrow",
  "worldcup.knockout_pending": "Not yet decided",
  "worldcup.stage.last_32": "Round of 32",
  "worldcup.stage.last_16": "Round of 16",
  "worldcup.stage.quarter": "Quarter-finals",
  "worldcup.stage.semi": "Semi-finals",
  "worldcup.stage.third": "Third place",
  "worldcup.stage.final": "Final",
```

- [ ] **Step 3: Verify JSON + typecheck**

Run: `cd frontend && node -e "JSON.parse(require('fs').readFileSync('src/locales/de.json'));JSON.parse(require('fs').readFileSync('src/locales/en.json'));console.log('ok')" && npx tsc --noEmit`
Expected: prints `ok`, no type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/locales/de.json frontend/src/locales/en.json
git commit -m "feat(worldcup): i18n strings for new signage views"
```

---

## Task 15: Document the ready-made playlist

**Files:**
- Modify: `frontend/src/docs/de/admin-guide/digital-signage.md`
- Modify: `frontend/src/docs/en/admin-guide/digital-signage.md`

- [ ] **Step 1: Add a "WM-2026-Views" section (de)**

In `frontend/src/docs/de/admin-guide/digital-signage.md`, after the "Playlists erstellen" section, add:

```markdown
## WM-2026-Views

Für die Fußball-WM 2026 ist eine fertige Playlist **„WM 2026"** vorinstalliert
(unter **Signage → Playlists**). Sie rotiert fünf Vollbild-Screens:
Übersicht (heutige Spiele live mit Tor-Animation), Tabelle (Gruppen, 6 pro Seite),
Spiele (gestern/heute/morgen), K.-o.-Runde und Torschützen.

So nimmst du sie in Betrieb:

1. Trage unter **Einstellungen → WM** einen football-data.org API-Schlüssel ein.
2. Gib der Playlist „WM 2026" unter **Signage → Playlists** einen **Tag**, der zu
   deinem Gerät passt (z. B. `lobby`).

Reihenfolge und Anzeigedauer pro Screen kannst du wie bei jeder Playlist anpassen.
Die **Dauer** ist die Zeit pro Screen — bei der Tabelle die Zeit pro 6er-Seite
(zwei Seiten, also doppelte Gesamtzeit).
```

- [ ] **Step 2: Add the English equivalent (en)**

In `frontend/src/docs/en/admin-guide/digital-signage.md`, after the playlists section, add the same content translated to English (title "## World Cup 2026 views", same two setup steps and duration note).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/docs/de/admin-guide/digital-signage.md frontend/src/docs/en/admin-guide/digital-signage.md
git commit -m "docs(worldcup): document ready-made WM 2026 signage playlist"
```

---

## Task 16: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Backend suite**

Run: `cd backend && python -m pytest tests/test_worldcup_extra_feeds.py tests/test_worldcup_feed.py tests/test_worldcup_embed.py tests/test_worldcup_playlist_seed.py tests/test_admin_gate_audit.py tests/test_openapi_paths_snapshot.py -v`
Expected: all PASS.

- [ ] **Step 2: Frontend unit tests + typecheck**

Run: `cd frontend && npx vitest run src/components/worldcup src/pages/EmbedWorldCupPage.test.tsx && npx tsc --noEmit`
Expected: all PASS, no type errors.

- [ ] **Step 3: Manual UAT (preview)**

Configure a football-data.org API key in Settings → WM. Then, in the preview, load each URL with a short duration and confirm real data renders and that each page posts `embed-cycle-complete` (visible in the signage player preview by auto-advancing):
- `/embed/worldcup/standings?duration=8` → group tables page through 6→6.
- `/embed/worldcup/matches?duration=8` → gestern/heute/morgen.
- `/embed/worldcup/knockout?duration=8` → stages or pending state.
- `/embed/worldcup/scorers?duration=8` → top 10.

- [ ] **Step 4: Final commit (if any verification tweaks were needed)**

```bash
git add -A
git commit -m "test(worldcup): verification pass for WM 2026 signage views"
```
