"""v1.53: revenues table + extend upload_batches.kind to include 'revenues'

Adds the Umsatz (RG/GS — Rechnungsausgang / Gutschrift) ingestion target.
Rows come from the ``AswKpf_RG.txt`` ERP export (18-col tab-separated,
Latin-1), keyed by ``Vorgang Nr.`` so re-uploads upsert on PK.

The Sales dashboard's "Umsatz" KPI card and "Umsatzwachstum" chart now
source from this table (sum of wert_eur over the date window). GS
(credit note) rows carry a negative wert_eur and naturally reduce the
revenue total when summed.

Order-side KPIs (``avg_order_value``, ``total_orders``,
``orders-distribution``) still source from ``sales_records``.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "v1_53_revenues"
down_revision = "v1_52_offers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen the kind discriminator to include 'revenues'.
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers','revenues')",
    )

    op.create_table(
        "revenues",
        sa.Column("vorgang_nr", sa.String(length=50), primary_key=True),
        # Typ on the source row: 'RG' (Rechnung) or 'GS' (Gutschrift). GS
        # rows carry a negative wert_eur — kept on the same table so a
        # single SUM gives the net revenue.
        sa.Column("typ", sa.String(length=8), nullable=False),
        sa.Column("datum", sa.Date(), nullable=False),
        sa.Column("adr_nr", sa.String(length=50), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
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
    op.create_index("ix_revenues_datum", "revenues", ["datum"])
    op.create_index("ix_revenues_customer", "revenues", ["customer_name"])


def downgrade() -> None:
    op.drop_index("ix_revenues_customer", table_name="revenues")
    op.drop_index("ix_revenues_datum", table_name="revenues")
    op.drop_table("revenues")

    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers')",
    )
