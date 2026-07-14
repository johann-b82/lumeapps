"""v1.81: inspection_records.rsc — Kostenschlüssel filter.

The AswQs2151 export mixes real Qualitätsprüfung bookings (``RSC = 70000``)
with other stock-movement bookings (Fertigung, Lager, Sonderbuchungen —
``RSC`` values like 60000, 16000, 41000, "L 0725", …). Only ``RSC = 70000``
represents an actual inspection, so every KPI aggregation filters on it.

The value is kept as a String because roughly 10 % of rows carry an
alphanumeric ``L xxxx`` sonder-key that would break an integer column.

Backfill: pull ``RSC`` out of the ``raw`` JSONB column for all pre-v1.81
rows so re-uploading the file isn't required.
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_81_inspection_rsc"
down_revision = "v1_80_inspection_excluded"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inspection_records",
        sa.Column("rsc", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_inspection_records_rsc",
        "inspection_records",
        ["rsc"],
    )
    # Backfill from the raw JSONB blob so existing uploads don't need to
    # be re-ingested.
    op.execute(
        "UPDATE inspection_records SET rsc = raw->>'RSC' WHERE rsc IS NULL"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inspection_records_rsc",
        table_name="inspection_records",
    )
    op.drop_column("inspection_records", "rsc")
