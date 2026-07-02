"""v1.70: Finanzperspektive — Materialkostenquote schema

Two new tables for the Materialkostenquote KPI (material cost / revenue):

* ``material_movements`` — AswLagBew.txt Lagerbewegung lines. No clean
  business key, so re-uploads are made idempotent by replace-by-date-range
  on ``buch_datum`` (the Kontakte pattern). Consumed qty per article =
  ``-SUM(bewegungsmenge)`` over ``buchtyp IN ('M','SM')``.
* ``material_prices`` — AswKpf_WE.txt Wareneingang lines, finance-scoped.
  Supplies the purchase price (effective unit price = ``pos_wert / menge`` of
  the newest WE row per Artnr). Business key ``(vorgang_nr, pos, upos)`` →
  ``ON CONFLICT DO UPDATE``. Deliberately distinct from the complaint-rate
  ``goods_receipt_records`` table so the Finanzperspektive stays self-contained.

Also extends ``ck_upload_batches_kind`` to permit ``material_movements``
and ``material_prices``.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "v1_70_finance_material_cost"
down_revision = "v1_69_quality_supplier_tgt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "material_movements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "upload_batch_id",
            sa.Integer(),
            sa.ForeignKey("upload_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artikelnr", sa.String(length=50), nullable=False),
        sa.Column("article_name", sa.String(length=255), nullable=True),
        # Drives the KPI window and the replace-by-date-range delete (indexed).
        sa.Column("buch_datum", sa.Date(), nullable=True),
        # Signed: M issues negative, SM reversals positive.
        sa.Column("bewegungsmenge", sa.Numeric(15, 3), nullable=True),
        sa.Column("buchtyp", sa.String(length=10), nullable=True),
        sa.Column("kommentar", sa.Text(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw", JSONB(), nullable=True),
    )
    op.create_index(
        "ix_material_movements_buch_datum", "material_movements", ["buch_datum"]
    )
    op.create_index(
        "ix_material_movements_artikelnr", "material_movements", ["artikelnr"]
    )

    op.create_table(
        "material_prices",
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
        sa.Column("typ", sa.String(length=10), nullable=True),
        # Wareneingang date — the "newest date" for the price lookup (indexed).
        sa.Column("datum", sa.Date(), nullable=True),
        sa.Column("artnr", sa.String(length=50), nullable=False),
        sa.Column("article_name", sa.String(length=255), nullable=True),
        sa.Column("menge", sa.Numeric(15, 3), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("preis", sa.Numeric(15, 4), nullable=True),
        sa.Column("pos_wert", sa.Numeric(15, 2), nullable=True),
        sa.Column("raw", JSONB(), nullable=True),
        sa.UniqueConstraint(
            "vorgang_nr", "pos", "upos",
            name="uq_material_prices_vorgang_pos",
        ),
    )
    op.create_index("ix_material_prices_artnr", "material_prices", ["artnr"])
    op.create_index("ix_material_prices_datum", "material_prices", ["datum"])

    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers',"
        "'revenues','auftraege','deliveries','delivery_reliability','tippspiel',"
        "'goods_receipts','material_movements','material_prices')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers',"
        "'revenues','auftraege','deliveries','delivery_reliability','tippspiel',"
        "'goods_receipts')",
    )
    op.drop_index("ix_material_prices_datum", table_name="material_prices")
    op.drop_index("ix_material_prices_artnr", table_name="material_prices")
    op.drop_table("material_prices")
    op.drop_index(
        "ix_material_movements_artikelnr", table_name="material_movements"
    )
    op.drop_index(
        "ix_material_movements_buch_datum", table_name="material_movements"
    )
    op.drop_table("material_movements")
