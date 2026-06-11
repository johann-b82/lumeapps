"""v1.52: offers table + extend upload_batches.kind to include 'offers'

Adds the Angebote (sales-offer line) ingestion target. Rows come from
the ``AswKpf_ANG.txt`` ERP export (18-col tab-separated, Latin-1),
keyed by ``Vorgang Nr.`` so re-uploads upsert on PK.

The Vertriebsaktivität dashboard's "Angebote" KPI sources from this
table (SUM of value in EUR per ISO-week per Erfasser), replacing the
retired Kontakte ``comment LIKE 'ANGEBOT%'`` heuristic. The chart bar
therefore now represents €-volume per rep per week instead of a count.

Deliberately a separate table from ``sales_records`` — the AswKpf_AUF
ingest covers orders; mixing ANG rows into sales_records pollutes the
Auftragswert / chart / orders-distribution KPIs (lesson from a prior
attempt). Each kind of file lives in its own table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "v1_52_offers"
down_revision = "v1_51_interessenten"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen the kind discriminator to include 'offers'.
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers')",
    )

    op.create_table(
        "offers",
        sa.Column("vorgang_nr", sa.String(length=50), primary_key=True),
        sa.Column("datum", sa.Date(), nullable=False),
        sa.Column("erfasser", sa.String(length=64), nullable=True),
        sa.Column("wert_eur", sa.Numeric(15, 2), nullable=False),
        sa.Column("adr_nr", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("ort", sa.String(length=255), nullable=True),
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
    op.create_index("ix_offers_datum", "offers", ["datum"])
    op.create_index("ix_offers_erfasser_datum", "offers", ["erfasser", "datum"])


def downgrade() -> None:
    op.drop_index("ix_offers_erfasser_datum", table_name="offers")
    op.drop_index("ix_offers_datum", table_name="offers")
    op.drop_table("offers")

    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten')",
    )
