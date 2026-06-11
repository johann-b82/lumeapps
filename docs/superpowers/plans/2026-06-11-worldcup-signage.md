# World Cup Live Results Signage Embed — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public `/embed/worldcup` kiosk page showing today's FIFA World Cup matches live (poll every N seconds, default 60) with a full-screen goal animation, fed by a server-side-cached football-data.org proxy, configurable (API key + interval) in a new "World Cup" settings section.

**Architecture:** Backend-proxied feed mirroring the HR embed pattern: `backend/app/routers/worldcup.py` exposes public `GET /api/worldcup/embed/today`, backed by a module-level cache in `backend/app/services/worldcup_feed.py` (one upstream call per interval regardless of screen count). Settings live as two new columns on the `app_settings` singleton (Fernet-encrypted key + interval). Frontend adds a `worldcup` settings slice/section and a no-scroll embed page with client-side goal detection (score diff between polls).

**Tech Stack:** FastAPI + SQLAlchemy 2 async + Alembic + httpx (already a dependency) on the backend; React + TanStack Query + Tailwind + react-i18next on the frontend. Tests: pytest (backend, needs the compose stack's Postgres up), vitest (frontend).

**Spec:** `docs/superpowers/specs/2026-06-11-worldcup-signage-design.md`. One deliberate deviation: JSON field names are snake_case (`refresh_seconds`, `stale_since`, `kickoff_utc`, `next_matchday`) to match the house API style, not the camelCase sketch in the spec.

**Prerequisites:**
- Dev stack running: `docker compose up -d db api` (backend tests hit the real Postgres).
- Backend test commands below assume a host venv with backend deps. If the host has none, run the same pytest command inside the container instead: `docker compose exec api python -m pytest <args>`.

**File map:**

| File | Action | Responsibility |
|---|---|---|
| `backend/app/models/_base.py` | modify | 2 new `AppSettings` columns |
| `backend/alembic/versions/v1_57_worldcup.py` | create | migration for the 2 columns |
| `backend/app/schemas/_base.py` | modify | `SettingsRead`/`SettingsUpdate` worldcup fields |
| `backend/app/routers/settings.py` | modify | read/write the worldcup fields |
| `backend/app/services/worldcup_feed.py` | create | upstream fetch + mapping + cache (all feed logic) |
| `backend/app/routers/worldcup.py` | create | public embed endpoint (thin: settings lookup + delegate) |
| `backend/app/main.py` | modify | register router |
| `backend/tests/test_settings_worldcup.py` | create | settings round-trip tests |
| `backend/tests/test_worldcup_feed.py` | create | service unit tests (no DB/network) |
| `backend/tests/test_worldcup_embed.py` | create | endpoint tests (mocked upstream) |
| `backend/tests/test_admin_gate_audit.py` | modify | allowlist the public endpoint |
| `frontend/src/lib/api.ts` | modify | Settings types + feed types + public fetcher |
| `frontend/src/hooks/useSettingsDraft.ts` | modify | draft fields + `worldcup` slice |
| `frontend/src/contexts/SettingsDraftContext.tsx` | modify | `SettingsSection` union |
| `frontend/src/hooks/useSettingsSection.ts` | modify | KNOWN set |
| `frontend/src/components/SettingsSectionPicker.tsx` | modify | SECTIONS list |
| `frontend/src/components/settings/WorldCupSettingsCard.tsx` | create | API key + interval inputs |
| `frontend/src/pages/WorldCupSettingsPage.tsx` | create | settings page (SalesSettingsPage clone) |
| `frontend/src/components/worldcup/goalDetection.ts` | create | pure score-diff logic |
| `frontend/src/components/worldcup/goalDetection.test.ts` | create | vitest for the diff |
| `frontend/src/components/worldcup/MatchCard.tsx` | create | one match tile |
| `frontend/src/components/worldcup/GoalOverlay.tsx` | create | full-screen goal animation |
| `frontend/src/pages/EmbedWorldCupPage.tsx` | create | kiosk page: polling, queueing, layout |
| `frontend/src/App.tsx` | modify | `/embed/worldcup` + `/settings/worldcup` routes |
| `frontend/src/locales/de.json`, `en.json` | modify | i18n keys (flat-key files) |
| `frontend/src/index.css` | modify | goal animation keyframes |

---

### Task 1: AppSettings columns + Alembic migration

**Files:**
- Modify: `backend/app/models/_base.py` (after the sensor block, ~line 200, inside `class AppSettings`)
- Create: `backend/alembic/versions/v1_57_worldcup.py`

- [ ] **Step 1: Add columns to the model**

In `backend/app/models/_base.py`, inside `class AppSettings`, directly after the `sensor_humidity_max` column:

```python
    # v1.57 — World Cup signage embed (football-data.org). Key is
    # Fernet-encrypted like the Personio credentials above.
    worldcup_api_key_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    worldcup_refresh_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60
    )
```

(`BYTEA` and `Integer` are already imported in this module — verify, don't re-import.)

- [ ] **Step 2: Create the migration**

Create `backend/alembic/versions/v1_57_worldcup.py`:

```python
"""v1.57: app_settings World Cup signage columns

Adds the football-data.org API key (Fernet-encrypted, like the Personio
credentials) and the embed refresh interval for the /embed/worldcup
signage page. server_default 60 backfills the existing singleton row.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v1_57_worldcup"
down_revision = "v1_56_sales_target_orep"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("worldcup_api_key_enc", postgresql.BYTEA(), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "worldcup_refresh_seconds",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "worldcup_refresh_seconds")
    op.drop_column("app_settings", "worldcup_api_key_enc")
```

- [ ] **Step 3: Apply the migration**

Run: `docker compose run --rm migrate` (or `docker compose exec api alembic upgrade head` if the migrate service isn't standalone-runnable).
Expected: log line `Running upgrade v1_56_sales_target_orep -> v1_57_worldcup`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/_base.py backend/alembic/versions/v1_57_worldcup.py
git commit -m "feat(worldcup): app_settings columns for football-data.org key + refresh interval"
```

---

### Task 2: Settings API read/write (TDD)

**Files:**
- Test: `backend/tests/test_settings_worldcup.py`
- Modify: `backend/app/schemas/_base.py` (SettingsUpdate ~line 165, SettingsRead ~line 204)
- Modify: `backend/app/routers/settings.py` (`_build_read` ~line 100, `put_settings` ~line 283)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_settings_worldcup.py`:

```python
"""Settings read/write coverage for the World Cup signage fields (v1.57).

The API key is write-only: PUT accepts `worldcup_api_key`, GET/PUT responses
expose only `worldcup_has_api_key`. None/omitted means "don't change",
mirroring the Personio credential pattern.
"""
import pytest

_CORE = [
    "color_primary",
    "color_accent",
    "color_background",
    "color_foreground",
    "color_muted",
    "color_destructive",
    "app_name",
]


async def _core_payload(client) -> dict:
    base = (await client.get("/api/settings")).json()
    return {k: base[k] for k in _CORE}


@pytest.mark.asyncio
async def test_worldcup_settings_roundtrip(admin_client):
    payload = await _core_payload(admin_client)
    payload["worldcup_api_key"] = "test-key-123"
    payload["worldcup_refresh_seconds"] = 120
    r = await admin_client.put("/api/settings", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["worldcup_has_api_key"] is True
    assert body["worldcup_refresh_seconds"] == 120
    assert "worldcup_api_key" not in body  # never echo the key


@pytest.mark.asyncio
async def test_worldcup_refresh_bounds(admin_client):
    payload = await _core_payload(admin_client)
    for bad in (10, 5000):
        r = await admin_client.put(
            "/api/settings", json={**payload, "worldcup_refresh_seconds": bad}
        )
        assert r.status_code == 422, f"expected 422 for {bad}"


@pytest.mark.asyncio
async def test_worldcup_key_preserved_when_omitted(admin_client):
    payload = await _core_payload(admin_client)
    r = await admin_client.put(
        "/api/settings", json={**payload, "worldcup_api_key": "k1"}
    )
    assert r.json()["worldcup_has_api_key"] is True
    # PUT without the key field must not clear the stored key.
    r2 = await admin_client.put("/api/settings", json=payload)
    assert r2.json()["worldcup_has_api_key"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_settings_worldcup.py -v`
Expected: FAIL — `KeyError: 'worldcup_has_api_key'` (field not in response yet).

- [ ] **Step 3: Add schema fields**

In `backend/app/schemas/_base.py`, at the end of `SettingsUpdate` (after `sensor_humidity_max`):

```python
    # v1.57 World Cup signage — None means "don't change" (credential pattern).
    worldcup_api_key: str | None = None
    worldcup_refresh_seconds: int | None = Field(default=None, ge=30, le=3600)
```

At the end of `SettingsRead` (after `sensor_humidity_max`, before `model_config`):

```python
    # v1.57 World Cup signage — key is write-only, expose only the boolean.
    worldcup_has_api_key: bool = False
    worldcup_refresh_seconds: int = 60
```

- [ ] **Step 4: Wire into the settings router**

In `backend/app/routers/settings.py`, `_build_read(...)`: add to the `SettingsRead(...)` constructor call, after the `sensor_humidity_max=...` line:

```python
        # v1.57 World Cup signage
        worldcup_has_api_key=row.worldcup_api_key_enc is not None,
        worldcup_refresh_seconds=row.worldcup_refresh_seconds,
```

In `put_settings(...)`, after the sensor block (after the `sensor_humidity_max` assignment, before the `_CORE_FIELDS` reset-detection comment):

```python
    # v1.57 World Cup signage — None means "don't change"
    if payload.worldcup_api_key is not None:
        row.worldcup_api_key_enc = encrypt_credential(payload.worldcup_api_key)
    if payload.worldcup_refresh_seconds is not None:
        row.worldcup_refresh_seconds = payload.worldcup_refresh_seconds
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_settings_worldcup.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/_base.py backend/app/routers/settings.py backend/tests/test_settings_worldcup.py
git commit -m "feat(worldcup): settings API for API key (write-only) + refresh interval"
```

---

### Task 3: Feed service — mapping, cache, stale handling (TDD)

**Files:**
- Test: `backend/tests/test_worldcup_feed.py`
- Create: `backend/app/services/worldcup_feed.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_worldcup_feed.py`:

```python
"""Unit tests for app/services/worldcup_feed.py — no DB, no network.

Upstream and clock are injected via monkeypatch on module globals
(`_fetch_upstream`, `_utcnow`); `reset_cache()` isolates tests.
"""
from datetime import date, datetime, timezone

import httpx
import pytest

from app.services import worldcup_feed as wcf


def _raw(id=1, utc="2026-06-11T19:00:00Z", status="IN_PLAY", home=1, away=0, minute=37):
    return {
        "id": id,
        "utcDate": utc,
        "status": status,
        "minute": minute,
        "homeTeam": {
            "name": "Deutschland", "shortName": "Germany", "tla": "GER",
            "crest": "https://crests.football-data.org/759.png",
        },
        "awayTeam": {
            "name": "Mexiko", "shortName": "Mexico", "tla": "MEX",
            "crest": "https://crests.football-data.org/769.png",
        },
        "score": {"fullTime": {"home": home, "away": away}},
    }


# --- build_feed (pure) ----------------------------------------------------

def test_build_feed_maps_today():
    feed = wcf.build_feed([_raw()], "Europe/Berlin", date(2026, 6, 11), 60)
    assert len(feed.matches) == 1
    m = feed.matches[0]
    assert m.home.name == "Deutschland"
    assert m.away.short_name == "Mexico"
    assert (m.score_home, m.score_away) == (1, 0)
    assert m.status == "IN_PLAY"
    assert m.minute == 37
    assert feed.next_matchday is None


def test_build_feed_berlin_date_boundary():
    # 23:00 UTC on the 11th is 01:00 on the 12th in Berlin (CEST) — not today.
    feed = wcf.build_feed(
        [_raw(utc="2026-06-11T23:00:00Z")], "Europe/Berlin", date(2026, 6, 11), 60
    )
    assert feed.matches == []
    assert feed.next_matchday == date(2026, 6, 12)
    assert len(feed.next_matches) == 1


def test_build_feed_next_matchday_only_when_today_empty():
    raws = [_raw(id=1), _raw(id=2, utc="2026-06-13T15:00:00Z")]
    feed = wcf.build_feed(raws, "Europe/Berlin", date(2026, 6, 11), 60)
    assert [m.id for m in feed.matches] == [1]
    assert feed.next_matchday is None


def test_build_feed_sorts_today_by_kickoff():
    raws = [_raw(id=2, utc="2026-06-11T19:00:00Z"), _raw(id=1, utc="2026-06-11T13:00:00Z")]
    feed = wcf.build_feed(raws, "Europe/Berlin", date(2026, 6, 11), 60)
    assert [m.id for m in feed.matches] == [1, 2]


def test_map_match_missing_score_and_minute():
    raw = _raw(status="TIMED")
    raw["score"] = {"fullTime": {"home": None, "away": None}}
    del raw["minute"]
    m = wcf.map_match(raw)
    assert m.score_home is None and m.score_away is None and m.minute is None


# --- get_feed (cache + stale) ----------------------------------------------

T0 = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_cache_serves_within_ttl(monkeypatch):
    wcf.reset_cache()
    calls = []

    async def fake_fetch(api_key, date_from, date_to):
        calls.append(api_key)
        return [_raw()]

    monkeypatch.setattr(wcf, "_fetch_upstream", fake_fetch)
    monkeypatch.setattr(wcf, "_utcnow", lambda: T0)
    f1 = await wcf.get_feed("k", 60, "Europe/Berlin")
    monkeypatch.setattr(wcf, "_utcnow", lambda: T0.replace(second=30))
    f2 = await wcf.get_feed("k", 60, "Europe/Berlin")
    assert calls == ["k"]  # second call served from cache
    assert f1.matches and f2.matches
    assert f2.stale_since is None


@pytest.mark.asyncio
async def test_cache_refetches_after_ttl(monkeypatch):
    wcf.reset_cache()
    calls = []

    async def fake_fetch(api_key, date_from, date_to):
        calls.append(1)
        return [_raw()]

    monkeypatch.setattr(wcf, "_fetch_upstream", fake_fetch)
    monkeypatch.setattr(wcf, "_utcnow", lambda: T0)
    await wcf.get_feed("k", 60, "Europe/Berlin")
    monkeypatch.setattr(wcf, "_utcnow", lambda: T0.replace(minute=2))
    await wcf.get_feed("k", 60, "Europe/Berlin")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_stale_served_on_upstream_failure(monkeypatch):
    wcf.reset_cache()
    state = {"fail": False}

    async def fake_fetch(api_key, date_from, date_to):
        if state["fail"]:
            raise httpx.ConnectError("boom")
        return [_raw()]

    monkeypatch.setattr(wcf, "_fetch_upstream", fake_fetch)
    monkeypatch.setattr(wcf, "_utcnow", lambda: T0)
    f1 = await wcf.get_feed("k", 60, "Europe/Berlin")
    assert f1.stale_since is None

    state["fail"] = True
    monkeypatch.setattr(wcf, "_utcnow", lambda: T0.replace(minute=2))
    f2 = await wcf.get_feed("k", 60, "Europe/Berlin")
    assert f2.matches, "stale data must still be served"
    assert f2.stale_since == T0
    assert f2.error is None


@pytest.mark.asyncio
async def test_error_flag_when_never_fetched(monkeypatch):
    wcf.reset_cache()

    async def fake_fetch(api_key, date_from, date_to):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(wcf, "_fetch_upstream", fake_fetch)
    f = await wcf.get_feed("k", 60, "Europe/Berlin")
    assert f.matches == []
    assert f.error == "upstream_unavailable"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_worldcup_feed.py -v`
Expected: FAIL at collection — `ModuleNotFoundError: No module named 'app.services.worldcup_feed'`.

- [ ] **Step 3: Implement the service**

Create `backend/app/services/worldcup_feed.py`:

```python
"""football-data.org → World Cup signage feed: mapping + module-level cache.

Used by routers/worldcup.py. The cache is module-level so one upstream call
per refresh interval serves every kiosk, regardless of screen count. On
upstream failure the last good data keeps being served with `stale_since`
set — a signage screen must never go blank. `reset_cache()` exists for tests
(it also recreates the asyncio.Lock so per-test event loops don't clash).
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
COMPETITION_CODE = "WC"
LOOKAHEAD_DAYS = 14  # one query covers today + the next-matchday fallback


class WorldCupTeam(BaseModel):
    name: str
    short_name: str | None = None
    crest: str | None = None


class WorldCupMatch(BaseModel):
    id: int
    home: WorldCupTeam
    away: WorldCupTeam
    score_home: int | None = None
    score_away: int | None = None
    status: str  # SCHEDULED/TIMED/IN_PLAY/PAUSED/FINISHED/...
    minute: int | None = None
    kickoff_utc: datetime


class WorldCupFeed(BaseModel):
    refresh_seconds: int
    stale_since: datetime | None = None
    error: str | None = None  # "not_configured" | "upstream_unavailable"
    matches: list[WorldCupMatch] = []
    next_matchday: date | None = None
    next_matches: list[WorldCupMatch] = []


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def map_match(raw: dict[str, Any]) -> WorldCupMatch:
    def team(side: str) -> WorldCupTeam:
        t = raw.get(side) or {}
        return WorldCupTeam(
            name=t.get("name") or t.get("shortName") or "?",
            short_name=t.get("shortName") or t.get("tla"),
            crest=t.get("crest"),
        )

    full_time = (raw.get("score") or {}).get("fullTime") or {}
    return WorldCupMatch(
        id=raw["id"],
        home=team("homeTeam"),
        away=team("awayTeam"),
        score_home=full_time.get("home"),
        score_away=full_time.get("away"),
        status=raw.get("status") or "SCHEDULED",
        minute=raw.get("minute"),
        kickoff_utc=raw["utcDate"],
    )


def build_feed(
    raw_matches: list[dict[str, Any]],
    tz_name: str,
    today: date,
    refresh_seconds: int,
) -> WorldCupFeed:
    tz = ZoneInfo(tz_name)
    todays: list[WorldCupMatch] = []
    future: dict[date, list[WorldCupMatch]] = {}
    for raw in raw_matches:
        m = map_match(raw)
        local_day = m.kickoff_utc.astimezone(tz).date()
        if local_day == today:
            todays.append(m)
        elif local_day > today:
            future.setdefault(local_day, []).append(m)
    todays.sort(key=lambda m: m.kickoff_utc)
    feed = WorldCupFeed(refresh_seconds=refresh_seconds, matches=todays)
    if not todays and future:
        next_day = min(future)
        feed.next_matchday = next_day
        feed.next_matches = sorted(future[next_day], key=lambda m: m.kickoff_utc)
    return feed


async def _fetch_upstream(
    api_key: str, date_from: date, date_to: date
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{FOOTBALL_DATA_BASE}/competitions/{COMPETITION_CODE}/matches",
            params={
                "dateFrom": date_from.isoformat(),
                "dateTo": date_to.isoformat(),
            },
            headers={"X-Auth-Token": api_key},
        )
        resp.raise_for_status()
        return resp.json().get("matches", [])


class _Cache:
    def __init__(self) -> None:
        self.raw: list[dict[str, Any]] | None = None
        self.fetched_at: datetime | None = None    # last successful fetch
        self.attempted_at: datetime | None = None  # last attempt (ok or not)
        self.lock = asyncio.Lock()


_cache = _Cache()


def reset_cache() -> None:
    global _cache
    _cache = _Cache()


async def get_feed(api_key: str, refresh_seconds: int, tz_name: str) -> WorldCupFeed:
    """Cached feed for 'today' in tz_name. At most one upstream attempt per
    refresh interval — failures also count as attempts so a dead upstream
    isn't hammered by every kiosk poll."""
    now = _utcnow()
    async with _cache.lock:
        due = (
            _cache.attempted_at is None
            or (now - _cache.attempted_at).total_seconds() >= refresh_seconds
        )
        if due:
            _cache.attempted_at = now
            today = now.astimezone(ZoneInfo(tz_name)).date()
            try:
                _cache.raw = await _fetch_upstream(
                    api_key, today, today + timedelta(days=LOOKAHEAD_DAYS)
                )
                _cache.fetched_at = now
            except (httpx.HTTPError, ValueError):
                pass  # keep last good raw; stale_since signals it below

        if _cache.raw is None:
            return WorldCupFeed(
                refresh_seconds=refresh_seconds, error="upstream_unavailable"
            )
        # Rebuild from cached raw each request so "today" stays correct
        # across midnight even on a cache hit.
        today = now.astimezone(ZoneInfo(tz_name)).date()
        feed = build_feed(_cache.raw, tz_name, today, refresh_seconds)
        if (
            _cache.fetched_at is not None
            and _cache.attempted_at is not None
            and _cache.fetched_at < _cache.attempted_at
        ):
            feed.stale_since = _cache.fetched_at
        return feed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_worldcup_feed.py -v`
Expected: 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/worldcup_feed.py backend/tests/test_worldcup_feed.py
git commit -m "feat(worldcup): football-data.org feed service with TTL cache + stale fallback"
```

---

### Task 4: Public embed router + registration + admin-gate allowlist (TDD)

**Files:**
- Test: `backend/tests/test_worldcup_embed.py`
- Create: `backend/app/routers/worldcup.py`
- Modify: `backend/app/main.py` (import block ~line 15, include_router block ~line 41)
- Modify: `backend/tests/test_admin_gate_audit.py` (`ADMIN_GATE_ALLOWLIST`, ~line 56)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_worldcup_embed.py`:

```python
"""Endpoint tests for the public GET /api/worldcup/embed/today route.

Upstream is mocked via monkeypatch on worldcup_feed._fetch_upstream; the
worldcup settings columns are set directly on the app_settings row because
the autouse reset_settings fixture only resets DEFAULT_SETTINGS keys.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import update

from app.models import AppSettings
from app.security.fernet import encrypt_credential
from app.services import worldcup_feed as wcf


@pytest.fixture(autouse=True)
def fresh_cache():
    wcf.reset_cache()
    yield
    wcf.reset_cache()


def _raw_match_now():
    # Kickoff "now" so the match is always on today's Berlin date.
    utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": 1,
        "utcDate": utc,
        "status": "IN_PLAY",
        "minute": 37,
        "homeTeam": {"name": "Deutschland", "shortName": "Germany", "tla": "GER", "crest": None},
        "awayTeam": {"name": "Mexiko", "shortName": "Mexico", "tla": "MEX", "crest": None},
        "score": {"fullTime": {"home": 1, "away": 0}},
    }


async def _set_worldcup(api_key_enc, refresh=60):
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as s:
        await s.execute(
            update(AppSettings)
            .where(AppSettings.id == 1)
            .values(worldcup_api_key_enc=api_key_enc, worldcup_refresh_seconds=refresh)
        )
        await s.commit()


@pytest.mark.asyncio
async def test_not_configured_returns_empty_feed(client):
    await _set_worldcup(None)
    r = await client.get("/api/worldcup/embed/today")
    assert r.status_code == 200
    body = r.json()
    assert body["error"] == "not_configured"
    assert body["matches"] == []


@pytest.mark.asyncio
async def test_today_feed_unauthenticated(client, monkeypatch):
    await _set_worldcup(encrypt_credential("test-key"), refresh=120)
    seen = {}

    async def fake_fetch(api_key, date_from, date_to):
        seen["key"] = api_key
        return [_raw_match_now()]

    monkeypatch.setattr(wcf, "_fetch_upstream", fake_fetch)
    r = await client.get("/api/worldcup/embed/today")  # no auth header — public
    assert r.status_code == 200
    body = r.json()
    assert seen["key"] == "test-key", "decrypted key must reach upstream"
    assert body["refresh_seconds"] == 120
    assert body["matches"][0]["home"]["name"] == "Deutschland"
    assert body["matches"][0]["status"] == "IN_PLAY"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_worldcup_embed.py -v`
Expected: FAIL — 404 on `/api/worldcup/embed/today` (router not registered).

- [ ] **Step 3: Implement the router**

Create `backend/app/routers/worldcup.py`:

```python
"""Public World Cup live-results endpoint for the digital-signage embed.

ALL endpoints in this module are PUBLIC (no auth) — same rationale as
hr_embed.py: iframed by kiosks that carry no Directus session. Exposed data
is public match information from football-data.org; the API key never
leaves the server. Listed in ADMIN_GATE_ALLOWLIST (test_admin_gate_audit).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import AppSettings
from app.security.fernet import decrypt_credential
from app.services.worldcup_feed import WorldCupFeed, get_feed

router = APIRouter(prefix="/api/worldcup", tags=["worldcup"])


@router.get("/embed/today", response_model=WorldCupFeed)
async def embed_today(
    db: AsyncSession = Depends(get_async_db_session),
) -> WorldCupFeed:
    row = (
        await db.execute(select(AppSettings).where(AppSettings.id == 1))
    ).scalar_one_or_none()
    refresh = row.worldcup_refresh_seconds if row is not None else 60
    if row is None or not row.worldcup_api_key_enc:
        return WorldCupFeed(refresh_seconds=refresh, error="not_configured")
    api_key = decrypt_credential(row.worldcup_api_key_enc)
    return await get_feed(api_key, refresh, row.timezone)
```

- [ ] **Step 4: Register in main.py**

In `backend/app/main.py`, add to the router import block:

```python
from app.routers.worldcup import router as worldcup_router
```

and after `app.include_router(auth_forward_router)`:

```python
app.include_router(worldcup_router)
```

- [ ] **Step 5: Allowlist the public route**

In `backend/tests/test_admin_gate_audit.py`, add to `ADMIN_GATE_ALLOWLIST` (before the closing brace):

```python
    # World Cup signage embed — public by design, mirrors the hr_embed
    # rationale (kiosks without a session). See routers/worldcup.py docstring.
    ("/api/worldcup/embed/today", frozenset({"GET"})),
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_worldcup_embed.py tests/test_admin_gate_audit.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/worldcup.py backend/app/main.py backend/tests/test_worldcup_embed.py backend/tests/test_admin_gate_audit.py
git commit -m "feat(worldcup): public /api/worldcup/embed/today endpoint"
```

---

### Task 5: Frontend API types + settings plumbing

**Files:**
- Modify: `frontend/src/lib/api.ts` (`Settings` ~line 219, `SettingsUpdatePayload` ~line 263, public fetchers ~line 458)
- Modify: `frontend/src/hooks/useSettingsDraft.ts` (DraftFields, settingsToDraft, draftToCacheSettings, draftToPutPayload, slice machinery)
- Modify: `frontend/src/contexts/SettingsDraftContext.tsx` (line 3)
- Modify: `frontend/src/hooks/useSettingsSection.ts` (KNOWN set)
- Modify: `frontend/src/components/SettingsSectionPicker.tsx` (SECTIONS)
- Modify: `frontend/src/locales/de.json`, `frontend/src/locales/en.json`

- [ ] **Step 1: api.ts — Settings fields, feed types, public fetcher**

In `interface Settings`, after `sensor_humidity_max`:

```ts
  // v1.57 World Cup signage — key is write-only, only the boolean is exposed.
  worldcup_has_api_key: boolean;
  worldcup_refresh_seconds: number;
```

In `interface SettingsUpdatePayload`, after the sensor fields:

```ts
  // v1.57 World Cup signage. undefined = "don't change".
  worldcup_api_key?: string;
  worldcup_refresh_seconds?: number;
```

At the end of the file (after `fetchJoinersRecentPublic`):

```ts
// --- World Cup signage embed (v1.57) ---------------------------------------

export interface WorldCupTeam {
  name: string;
  short_name: string | null;
  crest: string | null;
}

export interface WorldCupMatch {
  id: number;
  home: WorldCupTeam;
  away: WorldCupTeam;
  score_home: number | null;
  score_away: number | null;
  status: string; // SCHEDULED/TIMED/IN_PLAY/PAUSED/FINISHED/...
  minute: number | null;
  kickoff_utc: string;
}

export interface WorldCupFeed {
  refresh_seconds: number;
  stale_since: string | null;
  error: string | null; // "not_configured" | "upstream_unavailable"
  matches: WorldCupMatch[];
  next_matchday: string | null;
  next_matches: WorldCupMatch[];
}

// Unauthenticated fetcher for the /embed/worldcup signage view — same
// credentials-omit pattern as the HR embed fetchers above.
export async function fetchWorldCupTodayPublic(): Promise<WorldCupFeed> {
  const r = await fetch("/api/worldcup/embed/today", { credentials: "omit" });
  if (!r.ok) throw new Error(`worldcup embed fetch failed: ${r.status}`);
  return (await r.json()) as WorldCupFeed;
}
```

- [ ] **Step 2: useSettingsDraft.ts — draft fields + slice**

Add to `interface DraftFields` (end):

```ts
  // v1.57 World Cup signage — api key is write-only (not in Settings response)
  worldcup_api_key: string;
  worldcup_refresh_seconds: number;
```

In `settingsToDraft`, add to the returned object:

```ts
    worldcup_api_key: "",
    worldcup_refresh_seconds: s.worldcup_refresh_seconds ?? 60,
```

In `draftToCacheSettings`, add:

```ts
    worldcup_refresh_seconds: draft.worldcup_refresh_seconds,
```

In `draftToPutPayload`, add to the `payload` literal:

```ts
    worldcup_refresh_seconds: draft.worldcup_refresh_seconds,
```

and after the `personio_client_secret` conditional:

```ts
  if (draft.worldcup_api_key) {
    payload.worldcup_api_key = draft.worldcup_api_key;
  }
```

Change the slice type and add the field list:

```ts
export type SettingsSlice = "general" | "hr" | "sales" | "worldcup";
```

```ts
const WORLDCUP_FIELDS = [
  "worldcup_api_key",
  "worldcup_refresh_seconds",
] as const satisfies readonly (keyof DraftFields)[];
```

Update `fieldsForSlice`:

```ts
function fieldsForSlice(slice: SettingsSlice): readonly (keyof DraftFields)[] {
  if (slice === "general") return GENERAL_FIELDS;
  if (slice === "hr") return HR_FIELDS;
  if (slice === "worldcup") return WORLDCUP_FIELDS;
  return SALES_FIELDS;
}
```

- [ ] **Step 3: Section registration**

`frontend/src/contexts/SettingsDraftContext.tsx` line 3:

```ts
export type SettingsSection = "general" | "hr" | "sensors" | "sales" | "worldcup";
```

`frontend/src/hooks/useSettingsSection.ts` — add `"worldcup"` to the `KNOWN` set.

`frontend/src/components/SettingsSectionPicker.tsx` line 16:

```ts
const SECTIONS: SettingsSection[] = ["general", "hr", "sensors", "sales", "worldcup"];
```

- [ ] **Step 4: i18n section key**

Both locale files are FLAT key-value JSON. Next to `"settings.section.sales"` add:

`de.json`: `"settings.section.worldcup": "WM",`
`en.json`: `"settings.section.worldcup": "World Cup",`

- [ ] **Step 5: Verify type-check passes**

Run: `cd frontend && npm run build`
Expected: build succeeds, no TS errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/hooks/useSettingsDraft.ts frontend/src/contexts/SettingsDraftContext.tsx frontend/src/hooks/useSettingsSection.ts frontend/src/components/SettingsSectionPicker.tsx frontend/src/locales/de.json frontend/src/locales/en.json
git commit -m "feat(worldcup): frontend settings slice + feed types + public fetcher"
```

---

### Task 6: World Cup settings card + page + route

**Files:**
- Create: `frontend/src/components/settings/WorldCupSettingsCard.tsx`
- Create: `frontend/src/pages/WorldCupSettingsPage.tsx`
- Modify: `frontend/src/App.tsx` (settings routes ~line 85)
- Modify: `frontend/src/locales/de.json`, `en.json`

- [ ] **Step 1: Settings card**

Create `frontend/src/components/settings/WorldCupSettingsCard.tsx`:

```tsx
import { useTranslation } from "react-i18next";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DraftFields } from "@/hooks/useSettingsDraft";

interface WorldCupSettingsCardProps {
  draft: DraftFields;
  setField: <K extends keyof DraftFields>(field: K, value: DraftFields[K]) => void;
  /** From Settings.worldcup_has_api_key — the key itself is write-only. */
  hasApiKey: boolean;
}

export function WorldCupSettingsCard({ draft, setField, hasApiKey }: WorldCupSettingsCardProps) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl font-semibold">{t("settings.worldcup.title")}</CardTitle>
        <p className="text-sm text-muted-foreground">{t("settings.worldcup.description")}</p>
      </CardHeader>
      <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="worldcup-api-key" className="text-sm font-medium">
            {t("settings.worldcup.api_key.label")}
          </Label>
          <Input
            id="worldcup-api-key"
            type="password"
            autoComplete="new-password"
            value={draft.worldcup_api_key}
            onChange={(e) => setField("worldcup_api_key", e.target.value)}
            placeholder={t("settings.worldcup.api_key.placeholder")}
          />
          {hasApiKey && !draft.worldcup_api_key && (
            <p className="text-xs text-muted-foreground">
              {t("settings.worldcup.api_key.saved_hint")}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="worldcup-refresh" className="text-sm font-medium">
            {t("settings.worldcup.refresh.label")}
          </Label>
          <Input
            id="worldcup-refresh"
            type="number"
            min={30}
            max={3600}
            value={String(draft.worldcup_refresh_seconds)}
            onChange={(e) => {
              const num = parseInt(e.target.value, 10);
              if (!isNaN(num)) setField("worldcup_refresh_seconds", num);
            }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Settings page**

Create `frontend/src/pages/WorldCupSettingsPage.tsx` — an exact structural clone of `frontend/src/pages/SalesSettingsPage.tsx` with these substitutions (copy that file, then apply):

- `SCOPE_PATH = "/settings/worldcup"`
- `useSettingsDraft({ slice: "worldcup" })`
- `data-testid="settings-page-worldcup"`
- Replace the `<SalesTargetsCard draft={draft} setField={setField} />` line with:

```tsx
          <WorldCupSettingsCard
            draft={draft}
            setField={setField}
            hasApiKey={settings?.worldcup_has_api_key ?? false}
          />
```

- Replace the SalesTargetsCard import with `import { WorldCupSettingsCard } from "@/components/settings/WorldCupSettingsCard";` and add `import { useSettings } from "@/hooks/useSettings";`
- Inside the component add: `const { data: settings } = useSettings();`
- Rename the component to `WorldCupSettingsPage`.

- [ ] **Step 3: Route**

In `frontend/src/App.tsx`: import `{ WorldCupSettingsPage }` next to the other settings page imports, and add after the `/settings/sales` route (before `/settings`):

```tsx
          <Route path="/settings/worldcup" component={WorldCupSettingsPage} />
```

- [ ] **Step 4: i18n keys**

Add flat keys to both locale files next to the other `settings.*` keys:

`de.json`:

```json
  "settings.worldcup.title": "WM-Anzeige",
  "settings.worldcup.description": "Live-Ergebnisse der FIFA WM für den Infobildschirm (/embed/worldcup). Datenquelle: football-data.org.",
  "settings.worldcup.api_key.label": "football-data.org API-Schlüssel",
  "settings.worldcup.api_key.placeholder": "API-Schlüssel eingeben",
  "settings.worldcup.api_key.saved_hint": "Schlüssel gespeichert — leer lassen, um ihn zu behalten.",
  "settings.worldcup.refresh.label": "Aktualisierung (Sekunden, 30–3600)",
```

`en.json`:

```json
  "settings.worldcup.title": "World Cup display",
  "settings.worldcup.description": "Live FIFA World Cup results for the signage screen (/embed/worldcup). Data source: football-data.org.",
  "settings.worldcup.api_key.label": "football-data.org API key",
  "settings.worldcup.api_key.placeholder": "Enter API key",
  "settings.worldcup.api_key.saved_hint": "Key saved — leave blank to keep it.",
  "settings.worldcup.refresh.label": "Refresh (seconds, 30–3600)",
```

- [ ] **Step 5: Verify build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/settings/WorldCupSettingsCard.tsx frontend/src/pages/WorldCupSettingsPage.tsx frontend/src/App.tsx frontend/src/locales/de.json frontend/src/locales/en.json
git commit -m "feat(worldcup): settings section with API key + refresh interval"
```

---

### Task 7: Goal detection logic (TDD)

**Files:**
- Test: `frontend/src/components/worldcup/goalDetection.test.ts`
- Create: `frontend/src/components/worldcup/goalDetection.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/worldcup/goalDetection.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { WorldCupMatch } from "@/lib/api";
import { detectGoals } from "./goalDetection";

function m(id: number, h: number | null, a: number | null): WorldCupMatch {
  return {
    id,
    home: { name: "Heim", short_name: "HEI", crest: null },
    away: { name: "Gast", short_name: "GAS", crest: null },
    score_home: h,
    score_away: a,
    status: "IN_PLAY",
    minute: 10,
    kickoff_utc: "2026-06-11T19:00:00Z",
  };
}

function asMap(...matches: WorldCupMatch[]): Map<number, WorldCupMatch> {
  return new Map(matches.map((x) => [x.id, x]));
}

describe("detectGoals", () => {
  it("returns no events on the first poll (prev null)", () => {
    expect(detectGoals(null, [m(1, 3, 1)])).toEqual([]);
  });

  it("detects a home goal", () => {
    const events = detectGoals(asMap(m(1, 0, 0)), [m(1, 1, 0)]);
    expect(events).toHaveLength(1);
    expect(events[0].team.name).toBe("Heim");
    expect(events[0].scoreHome).toBe(1);
    expect(events[0].scoreAway).toBe(0);
  });

  it("detects goals on both sides between polls", () => {
    const events = detectGoals(asMap(m(1, 0, 0)), [m(1, 1, 1)]);
    expect(events.map((e) => e.team.name).sort()).toEqual(["Gast", "Heim"]);
  });

  it("treats null scores as 0 (no event when null -> 0)", () => {
    expect(detectGoals(asMap(m(1, null, null)), [m(1, 0, 0)])).toEqual([]);
  });

  it("ignores downward score corrections", () => {
    expect(detectGoals(asMap(m(1, 2, 0)), [m(1, 1, 0)])).toEqual([]);
  });

  it("ignores matches not present in the previous poll", () => {
    expect(detectGoals(asMap(m(1, 0, 0)), [m(2, 1, 0)])).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/worldcup/goalDetection.test.ts`
Expected: FAIL — cannot resolve `./goalDetection`.

- [ ] **Step 3: Implement**

Create `frontend/src/components/worldcup/goalDetection.ts`:

```ts
import type { WorldCupMatch, WorldCupTeam } from "@/lib/api";

export interface GoalEvent {
  matchId: number;
  team: WorldCupTeam;
  scoreHome: number;
  scoreAway: number;
}

/**
 * Diff scores between two polls. prev === null means "first poll after page
 * load" — never fire then, or a kiosk restart would replay old goals.
 * Matches absent from prev (e.g. day rollover) are skipped for the same
 * reason. Downward corrections (upstream fixing a wrong score) are ignored.
 */
export function detectGoals(
  prev: Map<number, WorldCupMatch> | null,
  next: WorldCupMatch[],
): GoalEvent[] {
  if (!prev) return [];
  const events: GoalEvent[] = [];
  for (const match of next) {
    const before = prev.get(match.id);
    if (!before) continue;
    const prevHome = before.score_home ?? 0;
    const prevAway = before.score_away ?? 0;
    const nextHome = match.score_home ?? 0;
    const nextAway = match.score_away ?? 0;
    if (nextHome > prevHome) {
      events.push({ matchId: match.id, team: match.home, scoreHome: nextHome, scoreAway: nextAway });
    }
    if (nextAway > prevAway) {
      events.push({ matchId: match.id, team: match.away, scoreHome: nextHome, scoreAway: nextAway });
    }
  }
  return events;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/worldcup/goalDetection.test.ts`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/worldcup/goalDetection.ts frontend/src/components/worldcup/goalDetection.test.ts
git commit -m "feat(worldcup): goal detection diff with restart/correction guards"
```

---

### Task 8: Embed page — match grid, goal overlay, route

**Files:**
- Create: `frontend/src/components/worldcup/MatchCard.tsx`
- Create: `frontend/src/components/worldcup/GoalOverlay.tsx`
- Create: `frontend/src/pages/EmbedWorldCupPage.tsx`
- Modify: `frontend/src/App.tsx` (RootRouter, ~line 118)
- Modify: `frontend/src/index.css` (append keyframes)
- Modify: `frontend/src/locales/de.json`, `en.json`

- [ ] **Step 1: MatchCard**

Create `frontend/src/components/worldcup/MatchCard.tsx`:

```tsx
import { useTranslation } from "react-i18next";
import type { WorldCupMatch, WorldCupTeam } from "@/lib/api";

const LIVE_STATUSES = new Set(["IN_PLAY", "PAUSED"]);

function TeamBlock({ team, compact }: { team: WorldCupTeam; compact: boolean }) {
  const size = compact ? "h-10 w-10" : "h-24 w-24";
  return (
    <div className="flex flex-col items-center gap-2 min-w-0 flex-1">
      {team.crest ? (
        <img src={team.crest} alt="" className={`${size} object-contain`} />
      ) : (
        <div className={size} />
      )}
      <span className={`${compact ? "text-sm" : "text-2xl"} font-semibold text-center truncate w-full`}>
        {team.name}
      </span>
    </div>
  );
}

function StatusBadge({ match }: { match: WorldCupMatch }) {
  const { t, i18n } = useTranslation();
  if (match.status === "FINISHED") {
    return <span className="text-muted-foreground font-medium">{t("worldcup.ft")}</span>;
  }
  if (match.status === "PAUSED") {
    return <span className="text-primary font-semibold">{t("worldcup.ht")}</span>;
  }
  if (LIVE_STATUSES.has(match.status)) {
    return (
      <span className="flex items-center gap-2 text-destructive font-semibold animate-pulse">
        ● {match.minute != null ? `${match.minute}'` : t("worldcup.live")}
      </span>
    );
  }
  return (
    <span className="text-muted-foreground font-medium">
      {new Date(match.kickoff_utc).toLocaleTimeString(i18n.language, {
        hour: "2-digit",
        minute: "2-digit",
      })}
    </span>
  );
}

export function MatchCard({ match, compact = false }: { match: WorldCupMatch; compact?: boolean }) {
  const live = LIVE_STATUSES.has(match.status);
  const notStarted = match.status === "SCHEDULED" || match.status === "TIMED";
  const score = notStarted ? "– : –" : `${match.score_home ?? 0} : ${match.score_away ?? 0}`;
  return (
    <div
      className={`flex items-center justify-between rounded-2xl border-2 bg-card p-4 min-h-0 overflow-hidden ${
        live ? "border-destructive" : "border-border"
      }`}
    >
      <TeamBlock team={match.home} compact={compact} />
      <div className="flex flex-col items-center gap-2 px-4 shrink-0">
        <span className={`${compact ? "text-2xl" : "text-6xl"} font-bold tabular-nums whitespace-nowrap`}>
          {score}
        </span>
        <StatusBadge match={match} />
      </div>
      <TeamBlock team={match.away} compact={compact} />
    </div>
  );
}
```

- [ ] **Step 2: GoalOverlay + keyframes**

Create `frontend/src/components/worldcup/GoalOverlay.tsx`:

```tsx
import { useTranslation } from "react-i18next";
import type { GoalEvent } from "./goalDetection";

/** Full-screen goal celebration. Parent mounts/unmounts it on a timer. */
export function GoalOverlay({ goal }: { goal: GoalEvent }) {
  const { t } = useTranslation();
  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-8 bg-background/95 worldcup-goal-pop">
      <span className="text-[9rem] leading-none font-black tracking-tight worldcup-goal-flash">
        ⚽ {t("worldcup.goal")}
      </span>
      {goal.team.crest && (
        <img src={goal.team.crest} alt="" className="h-40 w-40 object-contain" />
      )}
      <span className="text-6xl font-bold">{goal.team.name}</span>
      <span className="text-7xl font-bold tabular-nums">
        {goal.scoreHome} : {goal.scoreAway}
      </span>
    </div>
  );
}
```

Append to `frontend/src/index.css`:

```css
/* World Cup signage goal overlay (EmbedWorldCupPage) */
@keyframes worldcup-goal-pop {
  0% { transform: scale(0.3); opacity: 0; }
  60% { transform: scale(1.08); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}
@keyframes worldcup-goal-flash {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
.worldcup-goal-pop { animation: worldcup-goal-pop 0.5s ease-out; }
.worldcup-goal-flash { animation: worldcup-goal-flash 1s ease-in-out infinite; }
```

- [ ] **Step 3: Embed page**

Create `frontend/src/pages/EmbedWorldCupPage.tsx`:

```tsx
/**
 * EmbedWorldCupPage — kiosk-friendly /embed/worldcup. Sibling of
 * EmbedBirthdaysPage: no admin shell, no auth, German default (?lang=en).
 * Polls the public worldcup feed at the server-configured interval and
 * fires a full-screen overlay when a score increases between polls.
 * No scrolling ever — the match grid auto-fits 1–6 matches.
 */
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  fetchWorldCupTodayPublic,
  type WorldCupFeed,
  type WorldCupMatch,
} from "@/lib/api";
import { detectGoals, type GoalEvent } from "@/components/worldcup/goalDetection";
import { MatchCard } from "@/components/worldcup/MatchCard";
import { GoalOverlay } from "@/components/worldcup/GoalOverlay";

const GOAL_OVERLAY_MS = 6000;

function gridClass(count: number): string {
  if (count <= 1) return "grid-cols-1";
  if (count === 2) return "grid-cols-2";
  if (count <= 4) return "grid-cols-2 grid-rows-2";
  return "grid-cols-3 grid-rows-2";
}

export function EmbedWorldCupPage() {
  const { t, i18n } = useTranslation();
  useEffect(() => {
    const lang = new URLSearchParams(window.location.search).get("lang") ?? "de";
    if (i18n.language !== lang) {
      void i18n.changeLanguage(lang);
    }
  }, [i18n]);

  const [refreshMs, setRefreshMs] = useState(60_000);
  const { data } = useQuery<WorldCupFeed>({
    queryKey: ["worldcup", "embed-today"],
    queryFn: fetchWorldCupTodayPublic,
    refetchInterval: refreshMs,
    refetchIntervalInBackground: true,
  });

  // Score diff between polls → goal overlay queue (sequential playback).
  const prevRef = useRef<Map<number, WorldCupMatch> | null>(null);
  const [goalQueue, setGoalQueue] = useState<GoalEvent[]>([]);

  useEffect(() => {
    if (!data) return;
    setRefreshMs(Math.max(30, data.refresh_seconds) * 1000);
    const events = detectGoals(prevRef.current, data.matches);
    if (events.length > 0) setGoalQueue((q) => [...q, ...events]);
    prevRef.current = new Map(data.matches.map((m) => [m.id, m]));
  }, [data]);

  const currentGoal = goalQueue[0] ?? null;
  useEffect(() => {
    if (!currentGoal) return;
    const timer = setTimeout(() => setGoalQueue((q) => q.slice(1)), GOAL_OVERLAY_MS);
    return () => clearTimeout(timer);
  }, [currentGoal]);

  const matches = data?.matches ?? [];
  const staleTime = data?.stale_since
    ? new Date(data.stale_since).toLocaleTimeString(i18n.language, {
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <div className="h-screen w-screen overflow-hidden bg-background flex flex-col p-6 gap-4">
      <header className="flex items-baseline justify-between shrink-0">
        <h1 className="text-3xl font-bold">{t("worldcup.title")}</h1>
        <div className="flex items-baseline gap-4">
          {staleTime && (
            <span className="text-sm text-muted-foreground">
              {t("worldcup.stale", { time: staleTime })}
            </span>
          )}
          <span className="text-3xl font-medium text-muted-foreground">
            {new Date().toLocaleDateString(i18n.language, {
              weekday: "long",
              day: "numeric",
              month: "long",
            })}
          </span>
        </div>
      </header>

      {matches.length > 0 ? (
        <div className={`grid flex-1 min-h-0 gap-4 ${gridClass(matches.length)}`}>
          {matches.map((m) => (
            <MatchCard key={m.id} match={m} />
          ))}
        </div>
      ) : (
        <EmptyState feed={data} />
      )}

      {currentGoal && <GoalOverlay goal={currentGoal} />}
    </div>
  );
}

function EmptyState({ feed }: { feed: WorldCupFeed | undefined }) {
  const { t, i18n } = useTranslation();
  if (!feed) return null;
  const headline =
    feed.error === "not_configured"
      ? t("worldcup.not_configured")
      : t("worldcup.no_matches");
  const nextDate = feed.next_matchday
    ? new Date(feed.next_matchday).toLocaleDateString(i18n.language, {
        weekday: "long",
        day: "numeric",
        month: "long",
      })
    : null;
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-8 min-h-0">
      <p className="text-5xl font-semibold text-center">{headline}</p>
      {nextDate && (
        <>
          <p className="text-2xl text-muted-foreground">
            {t("worldcup.next_matchday", { date: nextDate })}
          </p>
          <div className="grid grid-cols-3 gap-3">
            {feed.next_matches.slice(0, 6).map((m) => (
              <MatchCard key={m.id} match={m} compact />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Route**

In `frontend/src/App.tsx`: import `{ EmbedWorldCupPage }` next to the other embed imports and add inside `RootRouter`'s `Switch`, after `/embed/joiners`:

```tsx
      <Route path="/embed/worldcup" component={EmbedWorldCupPage} />
```

- [ ] **Step 5: i18n keys**

Add flat keys to both locale files (group near other feature keys):

`de.json`:

```json
  "worldcup.title": "WM heute",
  "worldcup.no_matches": "Heute keine Spiele",
  "worldcup.next_matchday": "Nächster Spieltag: {{date}}",
  "worldcup.goal": "TOR!",
  "worldcup.live": "LIVE",
  "worldcup.ht": "HZ",
  "worldcup.ft": "Ende",
  "worldcup.stale": "Stand: {{time}}",
  "worldcup.not_configured": "WM-Datenquelle nicht konfiguriert",
```

`en.json`:

```json
  "worldcup.title": "World Cup today",
  "worldcup.no_matches": "No matches today",
  "worldcup.next_matchday": "Next matchday: {{date}}",
  "worldcup.goal": "GOAL!",
  "worldcup.live": "LIVE",
  "worldcup.ht": "HT",
  "worldcup.ft": "FT",
  "worldcup.stale": "As of {{time}}",
  "worldcup.not_configured": "World Cup data source not configured",
```

- [ ] **Step 6: Verify build + tests**

Run: `cd frontend && npm run build && npx vitest run src/components/worldcup`
Expected: build OK, 6 tests pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/worldcup frontend/src/pages/EmbedWorldCupPage.tsx frontend/src/App.tsx frontend/src/index.css frontend/src/locales/de.json frontend/src/locales/en.json
git commit -m "feat(worldcup): /embed/worldcup kiosk page with goal overlay"
```

---

### Task 9: Full verification

- [ ] **Step 1: Backend suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: all pass (pre-existing failures unrelated to worldcup are out of scope — report them, don't fix).

- [ ] **Step 2: Frontend suite + build**

Run: `cd frontend && npx vitest run && npm run build`
Expected: all pass, build OK.

- [ ] **Step 3: Manual smoke (report instructions, needs a real API key)**

1. Register at https://www.football-data.org/client/register (free), copy the key.
2. Open `/settings` → section "WM" → paste the key, save.
3. Open `/embed/worldcup` — today's matches render (tournament started 2026-06-11); with no key the page shows the not-configured message instead of an error page.
4. Add the URL `/embed/worldcup` to a signage playlist as an iframe/URL tile like the existing HR embeds.

- [ ] **Step 4: Final commit (if any stragglers)**

```bash
git status   # should be clean of worldcup files
```
