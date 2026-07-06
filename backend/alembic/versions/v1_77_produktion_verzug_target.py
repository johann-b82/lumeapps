"""v1.77: Produktion — configurable Verzug target on app_settings

Adds ``app_settings.target_produktion_verzug`` — the max acceptable Verzugsquote
as a fraction (0.20 = 20 %). NULL hides the reference line on the Verzug chart
(same convention as the finance / HR targets).
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_77_produktion_verzug_target"
down_revision = "v1_76_produktion_verzug"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("target_produktion_verzug", sa.Numeric(8, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "target_produktion_verzug")
