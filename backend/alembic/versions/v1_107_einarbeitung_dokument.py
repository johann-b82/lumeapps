"""v1.107: Einarbeitungs-Vorgang — persistiertes Formular mit QR, Lebenszyklus
und Scan-Prüfung.

Der Einarbeitungsplan wird nicht mehr nur als PDF heruntergeladen, sondern als
Vorgang persistiert: ``doc_uid`` steckt als QR-Code auf dem Blatt und ordnet
einen hochgeladenen Scan zuverlässig wieder zu. Der frühere Laufweg auf dem
Formular wird durch die vier Zeitstempel (erstellt/uebergeben/zurueck/geprueft)
ersetzt. ``feld_layout`` hält die seitenrelativen Rechtecke der Pflichtfelder
für die halbautomatische Vollständigkeitsprüfung.

Revision ID: v1_107_einarbeitung_dokument
Revises: v1_106_stock_article_prices
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "v1_107_einarbeitung_dokument"
down_revision = "v1_106_stock_article_prices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "einarbeitung_dokument",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("doc_uid", sa.String(length=32), nullable=False),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("personio_employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("mitarbeiter_name", sa.Text(), nullable=False),
        sa.Column("stelle", sa.Text(), nullable=True),
        sa.Column("beginn", sa.Date(), nullable=True),
        sa.Column("abteilungen", JSONB(), nullable=True),
        sa.Column("pdf_uuid", sa.String(length=64), nullable=True),
        sa.Column("scan_uuid", sa.String(length=64), nullable=True),
        sa.Column("feld_layout", JSONB(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
            server_default="erstellt",
        ),
        sa.Column(
            "erstellt_am",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("uebergeben_am", sa.DateTime(timezone=True), nullable=True),
        sa.Column("zurueck_am", sa.DateTime(timezone=True), nullable=True),
        sa.Column("geprueft_am", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pruef_ergebnis", JSONB(), nullable=True),
        sa.Column("vollstaendig", sa.Boolean(), nullable=True),
        sa.Column("kommentar", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_einarbeitung_dokument_doc_uid",
        "einarbeitung_dokument",
        ["doc_uid"],
        unique=True,
    )
    op.create_index(
        "ix_einarbeitung_dokument_employee_id",
        "einarbeitung_dokument",
        ["employee_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_einarbeitung_dokument_employee_id", table_name="einarbeitung_dokument")
    op.drop_index("ix_einarbeitung_dokument_doc_uid", table_name="einarbeitung_dokument")
    op.drop_table("einarbeitung_dokument")
