"""v1.16 signage: add current_playlist_etag to signage_devices

Revision ID: v1_16_signage_devices_etag
Revises: v1_16_signage
Create Date: 2026-04-18

Adds signage_devices.current_playlist_etag (TEXT, nullable) so Phase 43
heartbeat endpoint can persist the player's last-known playlist ETag
(D-11 in 43-CONTEXT.md).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "v1_16_signage_devices_etag"
down_revision: str | None = "v1_16_signage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "signage_devices",
        sa.Column("current_playlist_etag", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("signage_devices", "current_playlist_etag")
