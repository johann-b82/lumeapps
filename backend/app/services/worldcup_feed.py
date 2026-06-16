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
from collections.abc import Awaitable, Callable
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


class MatchesWindowFeed(BaseModel):
    refresh_seconds: int
    stale_since: datetime | None = None
    error: str | None = None
    yesterday: list[WorldCupMatch] = []
    today: list[WorldCupMatch] = []
    tomorrow: list[WorldCupMatch] = []


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

# Extra feeds (standings/matches/knockout/scorers) each get their own cache
# entry so one upstream call per resource per interval serves every kiosk.
_caches: dict[str, _Cache] = {}


def reset_cache() -> None:
    global _cache
    _cache = _Cache()
    _caches.clear()


async def _cached_raw(
    key: str,
    refresh_seconds: int,
    fetch: Callable[[], Awaitable[list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]] | None, datetime | None]:
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
                position=r.get("position") or 0,
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
