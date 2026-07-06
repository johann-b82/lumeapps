"""v1.76: Produktion — auftrag_positionen (AUF order positions) + LS join index

Groundwork for the Produktionsperspektive KPI "Aufträge in Verzug". The
corrected ``AswKpf_AUF`` export is *position-level* (one row per order position),
structurally identical to the Lieferschein export, and carries a ``Lieferdatum``
per position (the confirmed Zieltermin). This is a distinct dataset from the
order-book ``auftraege`` table (Sales), so it gets its own table mirroring
``delivery_records``.

Verzug (Gesamtfertigstellung): per order, MAX(LS delivery_date) − MAX(AUF
lieferdatum). The ``delivery_records.order_nr`` index speeds the LS side of that
per-order MAX/join.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "v1_76_produktion_verzug"
down_revision = "v1_75_fair_fields"
branch_labels = None
depends_on = None


_KIND_BASE = (
    "'orders','contacts','quality','interessenten','offers','revenues',"
    "'auftraege','deliveries','delivery_reliability','tippspiel',"
    "'goods_receipts','material_movements','material_prices'"
)


def upgrade() -> None:
    op.create_table(
        "auftrag_positionen",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "upload_batch_id",
            sa.Integer(),
            sa.ForeignKey("upload_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Business key: (vorgang_nr = order number, pos, upos).
        sa.Column("vorgang_nr", sa.String(length=50), nullable=False),
        sa.Column("pos", sa.Integer(), nullable=False),
        sa.Column("upos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("typ", sa.String(length=10), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=True),
        # Confirmed delivery date (Zieltermin) — the Verzug reference.
        sa.Column("lieferdatum", sa.Date(), nullable=True),
        sa.Column("customer_id", sa.String(length=50), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("customer_city", sa.String(length=255), nullable=True),
        sa.Column("article_number", sa.String(length=50), nullable=True),
        sa.Column("article_version", sa.String(length=50), nullable=True),
        sa.Column("article_name", sa.String(length=255), nullable=True),
        sa.Column("quantity", sa.Numeric(15, 3), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("price", sa.Numeric(15, 4), nullable=True),
        sa.Column("position_value", sa.Numeric(15, 2), nullable=True),
        # ERP "Pos Typ 2" (e.g. AV-F/AV-P/AV-S/OWB/AB) — the only classifier in
        # this export; reserved for a future Seriengeschäft filter.
        sa.Column("pos_typ_2", sa.String(length=20), nullable=True),
        sa.Column("external_order_nr", sa.String(length=100), nullable=True),
        sa.Column("raw", JSONB(), nullable=True),
        sa.UniqueConstraint(
            "vorgang_nr", "pos", "upos",
            name="uq_auftrag_positionen_vorgang_pos",
        ),
    )
    op.create_index(
        "ix_auftrag_positionen_vorgang_nr", "auftrag_positionen", ["vorgang_nr"]
    )
    op.create_index(
        "ix_auftrag_positionen_lieferdatum", "auftrag_positionen", ["lieferdatum"]
    )
    op.create_index(
        "ix_delivery_records_order_nr", "delivery_records", ["order_nr"]
    )

    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        f"kind IN ({_KIND_BASE},'auftrag_positionen')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        f"kind IN ({_KIND_BASE})",
    )
    op.drop_index("ix_delivery_records_order_nr", table_name="delivery_records")
    op.drop_index(
        "ix_auftrag_positionen_lieferdatum", table_name="auftrag_positionen"
    )
    op.drop_index(
        "ix_auftrag_positionen_vorgang_nr", table_name="auftrag_positionen"
    )
    op.drop_table("auftrag_positionen")
