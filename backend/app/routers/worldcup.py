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
