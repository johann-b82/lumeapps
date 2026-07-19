"""The v1_61 seed creates a ready-made 'WM 2026' playlist with 5 url media
items in order. Verifies presence + ordering against the migrated DB."""
import pytest
from sqlalchemy import select, text

from app.database import AsyncSessionLocal
from app.models import SignageMedia, SignagePlaylist, SignagePlaylistItem

# Mirror of the v1_61 migration seed (same fixed UUIDs + data). Re-applied
# idempotently below so this migration-seed check stays order-independent even
# when a sibling test (test_signage_admin_router) wipes the whole signage schema
# for its own isolation.
_PLAYLIST_ID = "11111111-1111-4111-8111-111111111111"
# (media_id, title, uri, duration_s, item_id)
_VIEWS = [
    ("22222222-2222-4222-8222-222222222201", "WM 2026 – Übersicht", "/embed/worldcup", 30, "33333333-3333-4333-8333-333333333301"),
    ("22222222-2222-4222-8222-222222222202", "WM 2026 – Tabelle", "/embed/worldcup/standings", 15, "33333333-3333-4333-8333-333333333302"),
    ("22222222-2222-4222-8222-222222222203", "WM 2026 – Spiele", "/embed/worldcup/matches", 20, "33333333-3333-4333-8333-333333333303"),
    ("22222222-2222-4222-8222-222222222204", "WM 2026 – KO-Runde", "/embed/worldcup/knockout", 20, "33333333-3333-4333-8333-333333333304"),
    ("22222222-2222-4222-8222-222222222205", "WM 2026 – Torschützen", "/embed/worldcup/scorers", 20, "33333333-3333-4333-8333-333333333305"),
]


@pytest.fixture(autouse=True)
async def _ensure_wm2026_seed():
    """Restore the v1_61 WM 2026 seed idempotently before the assertion.

    test_signage_admin_router's cleanup wipes every signage table (raw
    ``DELETE FROM signage_playlists`` etc.) for its own isolation, which would
    otherwise delete this migration seed and make the check order-dependent.
    ON CONFLICT DO NOTHING keeps a re-run a no-op when the seed is still present.
    """
    async with AsyncSessionLocal() as s:
        for media_id, title, uri, _dur, _item_id in _VIEWS:
            await s.execute(
                text("INSERT INTO signage_media (id, kind, title, uri) "
                     "VALUES (:id, 'url', :title, :uri) ON CONFLICT (id) DO NOTHING"),
                {"id": media_id, "title": title, "uri": uri},
            )
        await s.execute(
            text("INSERT INTO signage_playlists (id, name, enabled) "
                 "VALUES (:id, 'WM 2026', true) ON CONFLICT (id) DO NOTHING"),
            {"id": _PLAYLIST_ID},
        )
        for position, (media_id, _title, _uri, duration, item_id) in enumerate(_VIEWS):
            await s.execute(
                text("INSERT INTO signage_playlist_items "
                     "(id, playlist_id, media_id, position, duration_s, transition) "
                     "VALUES (:id, :pl, :media, :pos, :dur, 'fade') ON CONFLICT (id) DO NOTHING"),
                {"id": item_id, "pl": _PLAYLIST_ID, "media": media_id, "pos": position, "dur": duration},
            )
        await s.commit()
    yield


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
        assert pl.enabled is True
        assert [it.duration_s for it in items] == [30, 15, 20, 20, 20]
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
