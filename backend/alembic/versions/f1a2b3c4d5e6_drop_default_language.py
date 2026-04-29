"""Drop default_language column — language is now frontend-only (localStorage)

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-04-12
"""
import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("app_settings", "default_language")


def downgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("default_language", sa.String(2), nullable=False, server_default="EN"),
    )
