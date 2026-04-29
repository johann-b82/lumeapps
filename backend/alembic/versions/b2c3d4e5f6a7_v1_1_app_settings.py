"""v1.1 app_settings singleton

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-11
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import BYTEA

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

# Source of truth: backend/app/defaults.py
# These values are duplicated intentionally (migrations are snapshots and
# must not import live app code). Keep in sync if defaults.py ever changes.
_DEFAULT_ROW = {
    "id": 1,
    "color_primary": "oklch(0.55 0.15 250)",
    "color_accent": "oklch(0.70 0.18 150)",
    "color_background": "oklch(1.00 0 0)",
    "color_foreground": "oklch(0.15 0 0)",
    "color_muted": "oklch(0.90 0 0)",
    "color_destructive": "oklch(0.55 0.22 25)",
    "app_name": "KPI Light",
    "default_language": "EN",
    "logo_data": None,
    "logo_mime": None,
    "logo_updated_at": None,
}


def upgrade() -> None:
    settings = op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("color_primary", sa.String(64), nullable=False),
        sa.Column("color_accent", sa.String(64), nullable=False),
        sa.Column("color_background", sa.String(64), nullable=False),
        sa.Column("color_foreground", sa.String(64), nullable=False),
        sa.Column("color_muted", sa.String(64), nullable=False),
        sa.Column("color_destructive", sa.String(64), nullable=False),
        sa.Column("app_name", sa.String(100), nullable=False),
        sa.Column("default_language", sa.String(2), nullable=False),
        sa.Column("logo_data", BYTEA(), nullable=True),
        sa.Column("logo_mime", sa.String(64), nullable=True),
        sa.Column("logo_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_app_settings_singleton"),
    )
    op.bulk_insert(settings, [_DEFAULT_ROW])


def downgrade() -> None:
    op.drop_table("app_settings")
