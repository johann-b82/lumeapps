"""v1.67: Goods-receipt records + supplier classifications

Adds the two tables needed for the supplier-complaint rate denominator:

* ``goods_receipt_records`` — one row per AswKpf_WE Wareneingang-Position
  (the supplier-side counterpart of v1.58's ``delivery_records``). The
  date that drives the complaint-rate bucket is the ``receipt_date``
  (column O 'Lieferdatum' in the export).

* ``supplier_classifications`` — one row per supplier (Adressnummer)
  with a ``klasse_1`` value (e.g. 'MAT' for material). Populated from
  the dev_excel_LIE export; lets the dashboard restrict the
  goods-receipt denominator to "Material-Lieferanten" via JOIN.

Also extends ``ck_upload_batches_kind`` to permit the two new kinds.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "v1_67_goods_receipts"
down_revision = "v1_66_quality_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. goods_receipt_records — one row per WE position.
    op.create_table(
        "goods_receipt_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "upload_batch_id",
            sa.Integer(),
            sa.ForeignKey("upload_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Idempotency key, mirrors DeliveryRecord.
        sa.Column("vorgang_nr", sa.String(length=50), nullable=False),
        sa.Column("pos", sa.Integer(), nullable=False),
        sa.Column("upos", sa.Integer(), nullable=False, server_default="0"),

        sa.Column("typ", sa.String(length=10), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=True),
        sa.Column("receipt_date", sa.Date(), nullable=True),

        sa.Column("supplier_id", sa.String(length=50), nullable=True),
        sa.Column("supplier_name", sa.String(length=255), nullable=True),
        sa.Column("supplier_city", sa.String(length=255), nullable=True),

        sa.Column("article_number", sa.String(length=50), nullable=True),
        sa.Column("article_version", sa.String(length=50), nullable=True),
        sa.Column("article_name", sa.String(length=255), nullable=True),

        sa.Column("quantity", sa.Numeric(15, 3), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),

        sa.Column("price", sa.Numeric(15, 4), nullable=True),
        sa.Column("position_value", sa.Numeric(15, 2), nullable=True),

        sa.Column("order_nr", sa.String(length=100), nullable=True),
        sa.Column("order_date", sa.Date(), nullable=True),
        sa.Column("material_group", sa.String(length=50), nullable=True),
        sa.Column("purchase_account", sa.String(length=50), nullable=True),

        sa.Column("raw", JSONB(), nullable=True),

        sa.UniqueConstraint(
            "vorgang_nr", "pos", "upos",
            name="uq_goods_receipt_records_vorgang_pos",
        ),
    )
    op.create_index(
        "ix_goods_receipt_records_receipt_date",
        "goods_receipt_records",
        ["receipt_date"],
    )
    op.create_index(
        "ix_goods_receipt_records_supplier_date",
        "goods_receipt_records",
        ["supplier_id", "receipt_date"],
    )
    op.create_index(
        "ix_goods_receipt_records_material_group",
        "goods_receipt_records",
        ["material_group"],
    )

    # 2. supplier_classifications — supplier_id is the natural primary
    # key. We re-upload this table by replacing all rows on each upload
    # (it's stammdaten, not bewegungsdaten), so the surrogate id is
    # there only for ON CONFLICT / FK behaviour.
    op.create_table(
        "supplier_classifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "upload_batch_id",
            sa.Integer(),
            sa.ForeignKey("upload_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("supplier_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("supplier_name", sa.String(length=255), nullable=True),
        sa.Column("klasse_1", sa.String(length=50), nullable=True),
        sa.Column("klasse_2", sa.String(length=50), nullable=True),
        sa.Column("raw", JSONB(), nullable=True),
    )
    op.create_index(
        "ix_supplier_classifications_klasse_1",
        "supplier_classifications",
        ["klasse_1"],
    )

    # 3. Extend upload_batches.kind to permit the two new sources. The
    # constraint grew on parallel branches (interessenten, offers, revenues,
    # auftraege, delivery_reliability, tippspiel) — keep all of those
    # intact when adding goods_receipts and supplier_classes.
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers',"
        "'revenues','auftraege','deliveries','delivery_reliability',"
        "'tippspiel','goods_receipts','supplier_classes')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers',"
        "'revenues','auftraege','deliveries','delivery_reliability',"
        "'tippspiel')",
    )
    op.drop_index(
        "ix_supplier_classifications_klasse_1",
        table_name="supplier_classifications",
    )
    op.drop_table("supplier_classifications")
    op.drop_index(
        "ix_goods_receipt_records_material_group",
        table_name="goods_receipt_records",
    )
    op.drop_index(
        "ix_goods_receipt_records_supplier_date",
        table_name="goods_receipt_records",
    )
    op.drop_index(
        "ix_goods_receipt_records_receipt_date",
        table_name="goods_receipt_records",
    )
    op.drop_table("goods_receipt_records")
