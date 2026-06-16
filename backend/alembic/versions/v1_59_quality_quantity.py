"""v1.59: add quantity + accepted_quantity to quality_records

Columns from the 8D source (Spalte K "Menge" and L "akzeptierte Menge")
that drive the customer-complaint rate numerator. Both nullable — older
rows uploaded before v1.59 won't have them populated until the user
re-uploads the 8D file (the upsert path from v1.49 fills them in).
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_59_quality_quantity"
down_revision = "v1_58_delivery_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quality_records",
        sa.Column("quantity", sa.Numeric(15, 3), nullable=True),
    )
    op.add_column(
        "quality_records",
        sa.Column("accepted_quantity", sa.Numeric(15, 3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("quality_records", "accepted_quantity")
    op.drop_column("quality_records", "quantity")
