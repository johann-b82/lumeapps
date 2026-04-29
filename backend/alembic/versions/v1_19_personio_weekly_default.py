"""Raise Personio sync cadence default to weekly (168h)

Phase 60 follow-up — now that attendance fetch does a full first-run backfill
and incremental updates thereafter, a weekly sync is sufficient. Existing rows
still holding the old 1h default are bumped to 168; user-customized values
(anything other than 1) are left untouched.

Revision ID: v1_19_personio_weekly_default
Revises: v1_18_signage_heartbeat_event
Create Date: 2026-04-22
"""
import sqlalchemy as sa
from alembic import op

revision = "v1_19_personio_weekly_default"
down_revision = "v1_18_signage_heartbeat_event"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE app_settings SET personio_sync_interval_h = 168 "
        "WHERE personio_sync_interval_h = 1"
    )
    op.alter_column(
        "app_settings",
        "personio_sync_interval_h",
        server_default=sa.text("168"),
    )


def downgrade() -> None:
    op.alter_column(
        "app_settings",
        "personio_sync_interval_h",
        server_default=sa.text("1"),
    )
    op.execute(
        "UPDATE app_settings SET personio_sync_interval_h = 1 "
        "WHERE personio_sync_interval_h = 168"
    )
