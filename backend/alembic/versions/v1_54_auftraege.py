"""v1.54: auftraege table + extend upload_batches.kind to include 'auftraege'

Adds the Aufträge ingestion target for the new ``AswKpf_AUF.txt`` ERP
export (18-col tab-separated, Latin-1) — same shape as the ANG (offers)
and RG (revenues) dumps. Replaces the legacy 60-col ``20260430_Aufträge.txt``
format as the data source for the Sales-dashboard's order-side KPIs:
``avg_order_value``, ``total_orders``, ``orders/wk/rep``, ``top-3 customer
share``. The legacy ``sales_records`` table stays in place for back-compat
but no longer drives the dashboard.

Keyed by ``Vorgang Nr.`` so re-uploads upsert on PK.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "v1_54_auftraege"
down_revision = "v1_53_revenues"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen the kind discriminator to include 'auftraege'.
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers',"
        "'revenues','auftraege')",
    )

    op.create_table(
        "auftraege",
        sa.Column("vorgang_nr", sa.String(length=50), primary_key=True),
        sa.Column("typ", sa.String(length=8), nullable=False),
        sa.Column("datum", sa.Date(), nullable=False),
        sa.Column("adr_nr", sa.String(length=50), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("erfasser", sa.String(length=64), nullable=True),
        sa.Column("wert_eur", sa.Numeric(15, 2), nullable=False),
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
    op.create_index("ix_auftraege_datum", "auftraege", ["datum"])
    op.create_index("ix_auftraege_erfasser_datum", "auftraege", ["erfasser", "datum"])
    op.create_index("ix_auftraege_customer", "auftraege", ["customer_name"])


def downgrade() -> None:
    op.drop_index("ix_auftraege_customer", table_name="auftraege")
    op.drop_index("ix_auftraege_erfasser_datum", table_name="auftraege")
    op.drop_index("ix_auftraege_datum", table_name="auftraege")
    op.drop_table("auftraege")

    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers','revenues')",
    )
