"""The v1_61 seed creates a ready-made 'WM 2026' playlist with 5 url media
items in order. Verifies presence + ordering against the migrated DB."""
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
