"""v1.61: seed ready-made 'WM 2026' signage playlist

Creates 5 url media rows (the worldcup embed views), one playlist, and 5
playlist items in order. Fixed UUIDs + ON CONFLICT DO NOTHING make a re-run a
no-op and avoid resurrecting an admin-deleted row. No tag map — tags are
device-specific and assigned by the admin.
"""
from alembic import op
from sqlalchemy import text

revision = "v1_61_worldcup_playlist"
down_revision = "v1_60_procurement_otd"
branch_labels = None
depends_on = None

PLAYLIST_ID = "11111111-1111-4111-8111-111111111111"
# (media_id, title, uri, duration_s, item_id)
VIEWS = [
    ("22222222-2222-4222-8222-222222222201", "WM 2026 – Übersicht", "/embed/worldcup", 30, "33333333-3333-4333-8333-333333333301"),
    ("22222222-2222-4222-8222-222222222202", "WM 2026 – Tabelle", "/embed/worldcup/standings", 15, "33333333-3333-4333-8333-333333333302"),
    ("22222222-2222-4222-8222-222222222203", "WM 2026 – Spiele", "/embed/worldcup/matches", 20, "33333333-3333-4333-8333-333333333303"),
    ("22222222-2222-4222-8222-222222222204", "WM 2026 – KO-Runde", "/embed/worldcup/knockout", 20, "33333333-3333-4333-8333-333333333304"),
    ("22222222-2222-4222-8222-222222222205", "WM 2026 – Torschützen", "/embed/worldcup/scorers", 20, "33333333-3333-4333-8333-333333333305"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for media_id, title, uri, _duration, _item_id in VIEWS:
        conn.execute(
            text(
                "INSERT INTO signage_media (id, kind, title, uri) "
                "VALUES (:id, 'url', :title, :uri) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": media_id, "title": title, "uri": uri},
        )
    conn.execute(
        text(
            "INSERT INTO signage_playlists (id, name, enabled) "
            "VALUES (:id, 'WM 2026', true) ON CONFLICT (id) DO NOTHING"
        ),
        {"id": PLAYLIST_ID},
    )
    for position, (media_id, _title, _uri, duration, item_id) in enumerate(VIEWS):
        conn.execute(
            text(
                "INSERT INTO signage_playlist_items "
                "(id, playlist_id, media_id, position, duration_s, transition) "
                "VALUES (:id, :pl, :media, :pos, :dur, 'fade') "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": item_id, "pl": PLAYLIST_ID, "media": media_id, "pos": position, "dur": duration},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text("DELETE FROM signage_playlist_items WHERE playlist_id = :pl"),
        {"pl": PLAYLIST_ID},
    )
    conn.execute(text("DELETE FROM signage_playlists WHERE id = :pl"), {"pl": PLAYLIST_ID})
    for media_id, _title, _uri, _duration, _item_id in VIEWS:
        conn.execute(text("DELETE FROM signage_media WHERE id = :id"), {"id": media_id})
