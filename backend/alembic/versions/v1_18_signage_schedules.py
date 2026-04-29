"""v1.18 signage_schedules + app_settings.timezone — SGN-TIME-01

Creates ``signage_schedules`` for time-based playlist resolution and adds
``app_settings.timezone`` (VARCHAR(64) NOT NULL DEFAULT 'Europe/Berlin').

Per 51-CONTEXT.md D-01/D-05/D-06/D-07:
- Single migration handles both schema changes.
- Weekday mask is a 7-bit bitmap: bit 0=Monday..bit 6=Sunday.
- ``start_hhmm < end_hhmm`` CHECK rejects midnight-spanning windows (operators
  split such cases into two rows).
- Partial index on ``weekday_mask WHERE enabled=true`` trims hot-path scans.

Revision ID: v1_18_signage_schedules
Revises: v1_16_signage_devices_etag
Create Date: 2026-04-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "v1_18_signage_schedules"
down_revision: str | None = "v1_16_signage_devices_etag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add timezone column to app_settings — server_default backfills the
    #    singleton row atomically (Pitfall 6 — no separate UPDATE needed).
    op.add_column(
        "app_settings",
        sa.Column(
            "timezone",
            sa.String(64),
            nullable=False,
            server_default="Europe/Berlin",
        ),
    )

    # 2. Create signage_schedules table
    op.create_table(
        "signage_schedules",
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
                ondelete="RESTRICT",
                name="fk_signage_schedules_playlist_id",
            ),
            nullable=False,
        ),
        sa.Column("weekday_mask", sa.SmallInteger, nullable=False),
        sa.Column("start_hhmm", sa.Integer, nullable=False),
        sa.Column("end_hhmm", sa.Integer, nullable=False),
        sa.Column(
            "priority", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
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
        sa.CheckConstraint(
            "weekday_mask BETWEEN 0 AND 127",
            name="ck_signage_schedules_weekday_mask",
        ),
        sa.CheckConstraint(
            "start_hhmm >= 0 AND start_hhmm <= 2359",
            name="ck_signage_schedules_start_hhmm",
        ),
        sa.CheckConstraint(
            "end_hhmm >= 0 AND end_hhmm <= 2359",
            name="ck_signage_schedules_end_hhmm",
        ),
        sa.CheckConstraint(
            "start_hhmm < end_hhmm",
            name="ck_signage_schedules_no_midnight_span",
        ),
    )

    # 3. Partial index on the hot filter (enabled=true).
    op.create_index(
        "ix_signage_schedules_enabled_weekday",
        "signage_schedules",
        ["weekday_mask"],
        postgresql_where=sa.text("enabled = true"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_signage_schedules_enabled_weekday",
        table_name="signage_schedules",
    )
    op.drop_table("signage_schedules")
    op.drop_column("app_settings", "timezone")
