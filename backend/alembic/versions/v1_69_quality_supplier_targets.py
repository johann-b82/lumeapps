"""v1.69: Quality targets for Material Lieferanten + Werkbänke

Adds the two missing complaint-rate target columns on app_settings so
the supplier (LIE RE) and subcontractor / Werkbänke (UA RE) quotes get
the same configurable On-Quality threshold the customer + internal
ratios already have (v1.66).

Both nullable — NULL hides the chart's reference line (matches the
existing target_complaint_rate_customer / _internal pattern).
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_69_quality_supplier_tgt"
down_revision = "v1_68_drop_supplier_class"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("target_complaint_rate_supplier", sa.Numeric(8, 4), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "target_complaint_rate_subcontractor", sa.Numeric(8, 4), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "target_complaint_rate_subcontractor")
    op.drop_column("app_settings", "target_complaint_rate_supplier")
