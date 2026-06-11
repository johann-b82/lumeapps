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
