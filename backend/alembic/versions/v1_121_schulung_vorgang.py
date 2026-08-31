"""v1.121: Schulungsvorgang — persistiertes Formblatt 71 mit QR, Lebenszyklus,
Scan-Prüfung und zugeordneten Zertifikaten.

Analog zum Einarbeitungsvorgang (v1.107). ``schulung_dokument`` trägt QR-``doc_uid``,
vier Zeitstempel, Feld-Layout und Prüfergebnis; ``schulung_zertifikat`` hält die
je Schulungszeile hochgeladenen Nachweise.

Revision ID: v1_121_schulung_vorgang
Revises: v1_120_zeugnis_vorlage
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "v1_121_schulung_vorgang"
down_revision = "v1_120_zeugnis_vorlage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schulung_dokument",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("doc_uid", sa.String(length=32), nullable=False),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("personio_employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("mitarbeiter_name", sa.Text(), nullable=False),
        sa.Column("funktion", sa.Text(), nullable=True),
        sa.Column("pdf_uuid", sa.String(length=64), nullable=True),
        sa.Column("scan_uuid", sa.String(length=64), nullable=True),
        sa.Column("feld_layout", JSONB(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="erstellt"),
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
        "ix_schulung_dokument_doc_uid", "schulung_dokument", ["doc_uid"], unique=True
    )
    op.create_index(
        "ix_schulung_dokument_employee_id", "schulung_dokument", ["employee_id"]
    )

    op.create_table(
        "schulung_zertifikat",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "dokument_id",
            sa.Integer(),
            sa.ForeignKey("schulung_dokument.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("schulung_bezeichnung", sa.Text(), nullable=True),
        sa.Column("datei_uuid", sa.String(length=64), nullable=False),
        sa.Column("dateiname", sa.Text(), nullable=False),
        sa.Column(
            "hochgeladen_am",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_schulung_zertifikat_dokument_id", "schulung_zertifikat", ["dokument_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_schulung_zertifikat_dokument_id", table_name="schulung_zertifikat")
    op.drop_table("schulung_zertifikat")
    op.drop_index("ix_schulung_dokument_employee_id", table_name="schulung_dokument")
    op.drop_index("ix_schulung_dokument_doc_uid", table_name="schulung_dokument")
    op.drop_table("schulung_dokument")
