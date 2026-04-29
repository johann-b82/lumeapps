"""v1.16 signage schema — 8 tables for digital signage (SGN-DB-01..05)

Creates signage_media, signage_playlists, signage_playlist_items,
signage_devices, signage_device_tags, signage_device_tag_map,
signage_playlist_tag_map, signage_pairing_sessions.

Partial-unique index on signage_pairing_sessions.code WHERE active (SGN-DB-02).
ON DELETE RESTRICT on signage_playlist_items.media_id (SGN-DB-03).
CHECK constraints on kind and conversion_status (no ENUMs, round-trip clean).

Revision ID: v1_16_signage
Revises: v1_15_sensor
Create Date: 2026-04-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "v1_16_signage"
down_revision: str | None = "v1_15_sensor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ts_cols = lambda: [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    ]

    # 1. signage_media — no FK deps
    op.create_table(
        "signage_media",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(127), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("uri", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("conversion_status", sa.String(16), nullable=True),
        sa.Column("slide_paths", postgresql.JSONB, nullable=True),
        sa.Column("conversion_error", sa.Text, nullable=True),
        sa.Column("conversion_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("html_content", sa.Text, nullable=True),
        *ts_cols(),
        sa.CheckConstraint(
            "kind IN ('image','video','pdf','pptx','url','html')",
            name="ck_signage_media_kind",
        ),
        sa.CheckConstraint(
            "conversion_status IS NULL OR conversion_status IN ('pending','processing','done','failed')",
            name="ck_signage_media_conversion_status",
        ),
    )

    # 2. signage_playlists — no FK deps
    op.create_table(
        "signage_playlists",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *ts_cols(),
    )

    # 3. signage_device_tags — no FK deps
    op.create_table(
        "signage_device_tags",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False),
        *ts_cols(),
    )
    op.create_index(
        "uq_signage_device_tags_name",
        "signage_device_tags",
        ["name"],
        unique=True,
    )

    # 4. signage_devices — no FK deps
    op.create_table(
        "signage_devices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("device_token_hash", sa.Text, nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'offline'"),
        ),
        *ts_cols(),
        sa.CheckConstraint(
            "status IN ('online','offline','pending')",
            name="ck_signage_devices_status",
        ),
    )

    # 5. signage_playlist_items — FK playlist CASCADE, FK media RESTRICT (SGN-DB-03)
    op.create_table(
        "signage_playlist_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "playlist_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "signage_playlists.id",
                ondelete="CASCADE",
                name="fk_signage_playlist_items_playlist_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "media_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "signage_media.id",
                ondelete="RESTRICT",
                name="fk_signage_playlist_items_media_id",
            ),
            nullable=False,
        ),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("duration_s", sa.Integer, nullable=False, server_default=sa.text("10")),
        sa.Column("transition", sa.String(32), nullable=True),
        *ts_cols(),
    )
    op.create_index(
        "ix_signage_playlist_items_playlist_id",
        "signage_playlist_items",
        ["playlist_id"],
    )
    op.create_index(
        "ix_signage_playlist_items_media_id",
        "signage_playlist_items",
        ["media_id"],
    )

    # 6. signage_device_tag_map — composite PK, FKs CASCADE
    op.create_table(
        "signage_device_tag_map",
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "signage_devices.id",
                ondelete="CASCADE",
                name="fk_signage_device_tag_map_device_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            sa.Integer,
            sa.ForeignKey(
                "signage_device_tags.id",
                ondelete="CASCADE",
                name="fk_signage_device_tag_map_tag_id",
            ),
            nullable=False,
        ),
        *ts_cols(),
        sa.PrimaryKeyConstraint("device_id", "tag_id", name="pk_signage_device_tag_map"),
    )

    # 7. signage_playlist_tag_map — composite PK, FKs CASCADE
    op.create_table(
        "signage_playlist_tag_map",
        sa.Column(
            "playlist_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "signage_playlists.id",
                ondelete="CASCADE",
                name="fk_signage_playlist_tag_map_playlist_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            sa.Integer,
            sa.ForeignKey(
                "signage_device_tags.id",
                ondelete="CASCADE",
                name="fk_signage_playlist_tag_map_tag_id",
            ),
            nullable=False,
        ),
        *ts_cols(),
        sa.PrimaryKeyConstraint(
            "playlist_id", "tag_id", name="pk_signage_playlist_tag_map"
        ),
    )

    # 8. signage_pairing_sessions — FK device SET NULL, partial-unique index (SGN-DB-02)
    op.create_table(
        "signage_pairing_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(6), nullable=False),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "signage_devices.id",
                ondelete="SET NULL",
                name="fk_signage_pairing_sessions_device_id",
            ),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        *ts_cols(),
    )
    op.create_index(
        "uix_signage_pairing_sessions_code_active",
        "signage_pairing_sessions",
        ["code"],
        unique=True,
        # Note: `expires_at > now()` was removed from this predicate because
        # PostgreSQL requires functions in partial-index predicates to be
        # IMMUTABLE; `now()` is STABLE and is rejected at CREATE INDEX time
        # (errcode 42P17, "functions in index predicate must be marked
        # IMMUTABLE"). The active-pairing-session invariant is instead
        # enforced by the Phase 42 03:00 UTC cron cleanup which expires
        # rows by setting a terminal state. SGN-DB-02 amended 2026-04-18.
        postgresql_where=sa.text("claimed_at IS NULL"),
    )


def downgrade() -> None:
    # Drop partial unique index before its table (Pitfall 3)
    op.drop_index(
        "uix_signage_pairing_sessions_code_active",
        table_name="signage_pairing_sessions",
    )
    op.drop_table("signage_pairing_sessions")

    # Join tables (depend on devices, tags, playlists) — drop before parents
    op.drop_table("signage_playlist_tag_map")
    op.drop_table("signage_device_tag_map")

    # playlist_items depends on playlists + media — drop its indexes then table
    op.drop_index(
        "ix_signage_playlist_items_media_id",
        table_name="signage_playlist_items",
    )
    op.drop_index(
        "ix_signage_playlist_items_playlist_id",
        table_name="signage_playlist_items",
    )
    op.drop_table("signage_playlist_items")

    # Independent tables
    op.drop_table("signage_devices")
    op.drop_index("uq_signage_device_tags_name", table_name="signage_device_tags")
    op.drop_table("signage_device_tags")
    op.drop_table("signage_playlists")
    op.drop_table("signage_media")
