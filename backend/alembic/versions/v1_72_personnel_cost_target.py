"""v1.72: Finanzperspektive — personnel-cost-ratio target on app_settings

Adds the configurable target line for the Personalkostenquote chart. Stored as
a fraction (0.30 = 30 %), nullable — NULL hides the chart's reference line.
Mirrors v1.71's material-cost-ratio target.

NB: keep the revision id short — alembic_version.version_num is VARCHAR(32).
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_72_personnel_cost_target"
down_revision = "v1_71_material_cost_target"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("target_personnel_cost_ratio", sa.Numeric(8, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "target_personnel_cost_ratio")
