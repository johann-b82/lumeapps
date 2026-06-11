"""v1.57: app_settings World Cup signage columns

Adds the football-data.org API key (Fernet-encrypted, like the Personio
credentials) and the embed refresh interval for the /embed/worldcup
signage page. server_default 60 backfills the existing singleton row.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v1_57_worldcup"
down_revision = "v1_56_sales_target_orep"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("worldcup_api_key_enc", postgresql.BYTEA(), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "worldcup_refresh_seconds",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "worldcup_refresh_seconds")
    op.drop_column("app_settings", "worldcup_api_key_enc")
