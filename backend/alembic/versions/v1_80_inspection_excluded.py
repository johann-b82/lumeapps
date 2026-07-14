"""v1.80: inspection_records.excluded — per-booking KPI opt-out.

Adds a boolean flag so the user can mark individual inspection bookings
as "do not count" (e.g. the 52,7 M STK Abstandsgewirke fat-finger from
2026-06-29) without deleting the row. Every KPI query — cards, chart,
verification table — filters ``WHERE NOT excluded``.

Default ``false`` so pre-existing rows keep counting. Indexed because
the aggregation always joins on it.
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_80_inspection_excluded"
down_revision = "v1_79_inspection_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inspection_records",
        sa.Column(
            "excluded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_inspection_records_excluded",
        "inspection_records",
        ["excluded"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inspection_records_excluded",
        table_name="inspection_records",
    )
    op.drop_column("inspection_records", "excluded")
