"""v1.18 Phase 53 signage_heartbeat_event — SGN-ANA-01.

Creates the per-heartbeat append-only event log consumed by the
Analytics-lite endpoint. Composite PK (device_id, ts) — see
.planning/phases/53-analytics-lite/53-RESEARCH.md Pattern 2.

Revision ID: v1_18_signage_heartbeat_event
Revises: v1_18_signage_schedules
Create Date: 2026-04-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "v1_18_signage_heartbeat_event"
down_revision: str | None = "v1_18_signage_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signage_heartbeat_event",
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "signage_devices.id",
                ondelete="CASCADE",
                name="fk_signage_heartbeat_event_device_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "device_id", "ts", name="pk_signage_heartbeat_event"
        ),
    )
    # No secondary index — composite PK covers:
    #   (a) WHERE ts >= cutoff GROUP BY device_id  (analytics)
    #   (b) WHERE ts <  cutoff                     (sweeper prune)


def downgrade() -> None:
    op.drop_table("signage_heartbeat_event")
