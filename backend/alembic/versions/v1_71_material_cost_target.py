"""v1.71: Finanzperspektive — material-cost-ratio target on app_settings

Adds the configurable target line for the Materialkostenquote chart. Stored as
a fraction (0.15 = 15 %), nullable — NULL hides the chart's reference line.
Mirrors the v1.66 quality complaint-rate target columns.

NB: the revision id is kept short — alembic_version.version_num is
VARCHAR(32), so longer ids fail to persist.
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_71_material_cost_target"
down_revision = "v1_70_finance_material_cost"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("target_material_cost_ratio", sa.Numeric(8, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "target_material_cost_ratio")
