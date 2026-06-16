"""v1.58: Delivery records schema + extend upload_batches.kind

Adds `delivery_records` for the AswKpf_LS.xlsx Lieferschein export — one
row per Lieferschein-Position (i.e. one line-item on a delivery note).
The Quality dashboard uses ``Σ(delivery quantity)`` as the denominator of
the customer-complaint rate; the 8D records supply the numerator.

Idempotency key: ``(vorgang_nr, pos, upos)`` — the three columns the ERP
uses to identify a single LS line. Re-uploading the same file is a
no-op; an edited line is upserted via ``ON CONFLICT DO UPDATE`` on the
same composite key.

Also extends ``ck_upload_batches_kind`` to permit ``kind='deliveries'``.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "v1_58_delivery_schema"
down_revision = "v1_57_worldcup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. delivery_records — one row per LS position.
    op.create_table(
        "delivery_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "upload_batch_id",
            sa.Integer(),
            sa.ForeignKey("upload_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Business key. UNIQUE(vorgang_nr, pos, upos) is the upsert anchor.
        sa.Column("vorgang_nr", sa.String(length=50), nullable=False),
        sa.Column("pos", sa.Integer(), nullable=False),
        sa.Column("upos", sa.Integer(), nullable=False, server_default="0"),

        # "Typ" — the file only carries LS rows in practice; we still
        # store the column so a future filter can distinguish kinds.
        sa.Column("typ", sa.String(length=10), nullable=True),

        # Erfassungsdatum (Datum / column E) — recorded for auditing.
        sa.Column("entry_date", sa.Date(), nullable=True),
        # Lieferdatum (column O) — the date that drives the complaint
        # rate buckets. Indexed because every dashboard query filters on it.
        sa.Column("delivery_date", sa.Date(), nullable=True),

        sa.Column("customer_id", sa.String(length=50), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("customer_city", sa.String(length=255), nullable=True),

        sa.Column("article_number", sa.String(length=50), nullable=True),
        sa.Column("article_version", sa.String(length=50), nullable=True),
        sa.Column("article_name", sa.String(length=255), nullable=True),

        # NUMERIC for exact arithmetic (sums of quantities feed the
        # complaint-rate denominator; never use floats here).
        sa.Column("quantity", sa.Numeric(15, 3), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),

        sa.Column("price", sa.Numeric(15, 4), nullable=True),
        sa.Column("position_value", sa.Numeric(15, 2), nullable=True),

        sa.Column("external_order_nr", sa.String(length=100), nullable=True),
        sa.Column("order_nr", sa.String(length=100), nullable=True),

        sa.Column("raw", JSONB(), nullable=True),

        sa.UniqueConstraint(
            "vorgang_nr", "pos", "upos",
            name="uq_delivery_records_vorgang_pos",
        ),
    )
    op.create_index(
        "ix_delivery_records_delivery_date",
        "delivery_records",
        ["delivery_date"],
    )
    op.create_index(
        "ix_delivery_records_customer_date",
        "delivery_records",
        ["customer_id", "delivery_date"],
    )

    # 2. Extend upload_batches.kind to permit 'deliveries'.
    # The constraint grew over v1.51 (interessenten), v1.52 (offers),
    # v1.53 (revenues), v1.54 (auftraege) on the parallel branch — keep
    # all of those values intact when adding 'deliveries'.
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers',"
        "'revenues','auftraege','deliveries')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers',"
        "'revenues','auftraege')",
    )
    op.drop_index("ix_delivery_records_customer_date", table_name="delivery_records")
    op.drop_index("ix_delivery_records_delivery_date", table_name="delivery_records")
    op.drop_table("delivery_records")
