"""v1.60: Einkauf OTD — delivery_reliability schema + extend upload_batches.kind

Adds `delivery_reliability` for the dev_excel_Liefertreue_Einkauf.txt export —
one row per supplier delivery position. The Einkauf dashboard's
Liefertermintreue / OTD KPI counts punctual positions (``verzug_tage <= 0``)
over total positions within a window filtered on ``delivered_date``.

Idempotency key: ``(auftrag, pos, upos)`` — re-uploading the same file is a
no-op; an edited line is upserted via ``ON CONFLICT DO UPDATE`` on the same
composite key.

Also extends ``ck_upload_batches_kind`` to permit ``kind='delivery_reliability'``.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "v1_60_procurement_otd"
down_revision = "v1_59_quality_quantity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_reliability",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "upload_batch_id",
            sa.Integer(),
            sa.ForeignKey("upload_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Business key. UNIQUE(auftrag, pos, upos) is the upsert anchor.
        sa.Column("auftrag", sa.String(length=50), nullable=False),
        sa.Column("pos", sa.Integer(), nullable=False),
        sa.Column("upos", sa.Integer(), nullable=False, server_default="0"),

        sa.Column("adr_nr", sa.String(length=50), nullable=True),
        sa.Column("supplier_name", sa.String(length=255), nullable=True),

        # Actual goods-receipt date — drives the OTD window (indexed).
        sa.Column("delivered_date", sa.Date(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        # Signed delay in days; on-time classifier (≤ 0 = punctual).
        sa.Column("verzug_tage", sa.Integer(), nullable=True),

        sa.Column("quantity", sa.Numeric(15, 3), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),

        sa.Column("article_number", sa.String(length=50), nullable=True),
        sa.Column("article_name", sa.String(length=255), nullable=True),

        sa.Column("raw", JSONB(), nullable=True),

        sa.UniqueConstraint(
            "auftrag", "pos", "upos",
            name="uq_delivery_reliability_auftrag_pos",
        ),
    )
    op.create_index(
        "ix_delivery_reliability_delivered_date",
        "delivery_reliability",
        ["delivered_date"],
    )

    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers',"
        "'revenues','auftraege','deliveries','delivery_reliability')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers',"
        "'revenues','auftraege','deliveries')",
    )
    op.drop_index(
        "ix_delivery_reliability_delivered_date",
        table_name="delivery_reliability",
    )
    op.drop_table("delivery_reliability")
