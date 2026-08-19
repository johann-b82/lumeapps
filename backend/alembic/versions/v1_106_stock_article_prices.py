"""v1.106: Artikel-Preisliste (AswLagBew Preiskonditionen) für Lager-Bewertung.

Neue Tabelle ``stock_article_prices``: ein normierter Stückpreis je Artikel,
importiert aus der AswLagBew-Preisliste (``Wert ÷ Preismenge``). Speist die
Bewertung des Ladenhüter-Rankings „Bestellung auf Lager – Top 20" — dort wird
der Bestand (aus ``material_movements``) mit diesem Stückpreis multipliziert.

Voller Snapshot: der Upload ersetzt die Tabelle komplett (replace-all), da die
Preisliste ein Stammdaten-Abzug ohne Bewegungsdatum ist. Weitet zusätzlich den
``upload_batches.ck_upload_batches_kind`` CHECK auf ``'stock_prices'`` aus.

Revision ID: v1_106_stock_article_prices
Revises: v1_105_page_feedback
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_106_stock_article_prices"
down_revision = "v1_105_page_feedback"
branch_labels = None
depends_on = None


_KIND_VALUES_OLD = (
    "orders", "contacts", "quality", "interessenten", "offers",
    "revenues", "auftraege", "deliveries", "delivery_reliability",
    "tippspiel", "goods_receipts", "material_movements",
    "material_prices", "auftrag_positionen", "inspections",
)
_KIND_VALUES_NEW = (*_KIND_VALUES_OLD, "stock_prices")


def _kind_check(values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{v}'" for v in values)
    return f"kind IN ({joined})"


def upgrade() -> None:
    op.create_table(
        "stock_article_prices",
        sa.Column("artnr", sa.String(50), primary_key=True),
        sa.Column("unit_price", sa.Numeric(15, 5), nullable=False),
        sa.Column("price_unit", sa.String(20), nullable=True),
        sa.Column("article_name", sa.String(255), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Widen upload_batches.kind CHECK to accept the new 'stock_prices' kind.
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind", "upload_batches", _kind_check(_KIND_VALUES_NEW)
    )


def downgrade() -> None:
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind", "upload_batches", _kind_check(_KIND_VALUES_OLD)
    )
    op.drop_table("stock_article_prices")
