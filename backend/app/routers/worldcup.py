"""Public World Cup live-results endpoint for the digital-signage embed.

ALL endpoints in this module are PUBLIC (no auth) — same rationale as
hr_embed.py: iframed by kiosks that carry no Directus session. Exposed data
is public match information from football-data.org; the API key never
leaves the server. Listed in ADMIN_GATE_ALLOWLIST (test_admin_gate_audit).

Compute-justified: proxies football-data.org server-side (upstream HTTP
fetch + TTL cache in services/worldcup_feed.py) so the API key stays
secret and N kiosks cost one upstream call per interval — not a CRUD read.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import AppSettings, TippspielTip
from app.schemas import TippspielFeed, TippspielRankRow
from app.security.fernet import decrypt_credential
from app.services.tippspiel_scoring import compute_ranking
from app.services.worldcup_feed import (
    KnockoutFeed,
    MatchesWindowFeed,
    ScorersFeed,
    StandingsFeed,
    WorldCupFeed,
    get_feed,
    get_finished_results,
    get_knockout,
    get_matches_window,
    get_scorers,
    get_standings,
)

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


@router.get("/embed/tippspiel", response_model=TippspielFeed)
async def embed_tippspiel(
    db: AsyncSession = Depends(get_async_db_session),
) -> TippspielFeed:
    """Department ranking for the internal Tippspiel — stored tips scored
    against the live FINISHED results."""
    api_key, refresh, _ = await _settings(db)
    tip_rows = list((await db.execute(select(TippspielTip))).scalars().all())
    if not tip_rows:
        return TippspielFeed(refresh_seconds=refresh, ranking=[])

    departments = sorted({t.department for t in tip_rows})
    finished = (
        await get_finished_results(api_key, refresh) if api_key is not None else []
    )
    tips = [
        {
            "home": t.home_team,
            "away": t.away_team,
            "department": t.department,
            "tip_home": t.tip_home,
            "tip_away": t.tip_away,
        }
        for t in tip_rows
    ]
    ranking = compute_ranking(tips, finished, departments)
    return TippspielFeed(
        refresh_seconds=refresh,
        ranking=[TippspielRankRow(**r) for r in ranking],
    )
