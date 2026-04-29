"""v1.21 Phase 62-01 signage calibration columns — CAL-BE-01.

Adds three calibration columns to ``signage_devices``:
  - ``rotation``       INTEGER NOT NULL DEFAULT 0, CHECK IN (0, 90, 180, 270)
  - ``hdmi_mode``      VARCHAR(64) NULL — NULL means "use current" (D-02/D-07)
  - ``audio_enabled``  BOOLEAN NOT NULL DEFAULT false

Per CONTEXT D-07, the server_default on ALTER TABLE backfills every existing
row atomically — deployed devices keep current behaviour (rotation=0,
hdmi_mode=NULL, audio_enabled=false) with no flicker.

Revision ID: v1_21_signage_calibration
Revises: v1_19_personio_weekly_default
Create Date: 2026-04-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "v1_21_signage_calibration"
down_revision: str | None = "v1_19_personio_weekly_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "signage_devices",
        sa.Column(
            "rotation",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "signage_devices",
        sa.Column(
            "hdmi_mode",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "signage_devices",
        sa.Column(
            "audio_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_check_constraint(
        "ck_signage_devices_rotation",
        "signage_devices",
        "rotation IN (0, 90, 180, 270)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_signage_devices_rotation",
        "signage_devices",
        type_="check",
    )
    op.drop_column("signage_devices", "audio_enabled")
    op.drop_column("signage_devices", "hdmi_mode")
    op.drop_column("signage_devices", "rotation")
