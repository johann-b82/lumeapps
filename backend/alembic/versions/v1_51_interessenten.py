"""v1.51: interessenten table + extend upload_batches.kind to include 'interessenten'

Adds the Interessenten (prospect master-data) ingestion target. Rows
come from the ``dev_excel_INT.txt`` ERP export (88-col tab-separated,
Latin-1), keyed by ``Adress-Nr.`` so re-uploads upsert on PK rather
than inserting duplicates.

The Vertriebsaktivität dashboard's "Interessenten" KPI sources from
this table (count grouped by ISO-week of ``datum_save``), replacing the
retired Kontakte ``Typ IN ('ANFR','EPA')`` heuristic. The field
therefore moves from the per-employee bucket to a week-level total
in ``GET /api/data/sales/contacts-weekly`` (the source file has no
sales-rep column).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "v1_51_interessenten"
down_revision = "v1_50_signage_device_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen the kind discriminator to include 'interessenten'.
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten')",
    )

    op.create_table(
        "interessenten",
        sa.Column("adress_nr", sa.String(length=50), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("datum_save", sa.Date(), nullable=False),
        sa.Column(
            "upload_batch_id",
            sa.Integer(),
            sa.ForeignKey("upload_batches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("raw", JSONB(), nullable=True),
    )
    op.create_index(
        "ix_interessenten_datum_save", "interessenten", ["datum_save"]
    )


def downgrade() -> None:
    op.drop_index("ix_interessenten_datum_save", table_name="interessenten")
    op.drop_table("interessenten")

    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality')",
    )
