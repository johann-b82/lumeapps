"""v1.126: Produktion — Priorisierung (eigenständiges Modul, Tabellen ``prio_*``).

Stammdaten (Artikel, Ressourcenplan), offene BA-Positionen, importierte
Prioritätslisten, manuelle Reihenfolge und Import-Stand.

Revision ID: v1_126_produktion_prio
Revises: v1_125_inspection_total_target
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_126_produktion_prio"
down_revision = "v1_125_inspection_total_target"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prio_artikel",
        sa.Column("artikelnr", sa.String(length=64), primary_key=True),
        sa.Column("typ", sa.String(length=8), nullable=False),
        sa.Column("bezeichnung", sa.String(length=255), nullable=True),
        sa.Column("bezeichnung2", sa.String(length=255), nullable=True),
        sa.Column("einheit", sa.String(length=16), nullable=True),
    )
    op.create_table(
        "prio_plan_position",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("artikelnr", sa.String(length=64), nullable=False),
        sa.Column("pos", sa.Integer(), nullable=False),
        sa.Column("typ", sa.String(length=8), nullable=False),
        sa.Column("ref", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("menge", sa.Numeric(18, 6), nullable=True),
        sa.Column("einheit", sa.String(length=16), nullable=True),
        sa.Column("kostenstelle", sa.String(length=16), nullable=True),
        sa.Column("ruestzeit", sa.Numeric(14, 4), nullable=True),
        sa.Column("operativzeit", sa.Numeric(14, 4), nullable=True),
    )
    op.create_index("ix_prio_plan_position_artikel", "prio_plan_position", ["artikelnr", "pos"])
    op.create_table(
        "prio_auftrag_position",
        sa.Column("vorgang_nr", sa.String(length=32), primary_key=True),
        sa.Column("pos", sa.Integer(), primary_key=True),
        sa.Column("upos", sa.Integer(), primary_key=True),
        sa.Column("artikelnr", sa.String(length=64), nullable=True),
        sa.Column("bezeichnung", sa.String(length=255), nullable=True),
        sa.Column("menge", sa.Numeric(18, 4), nullable=True),
        sa.Column("einheit", sa.String(length=16), nullable=True),
        sa.Column("lieferdatum", sa.Date(), nullable=True),
        sa.Column("kunde_nr", sa.String(length=32), nullable=True),
        sa.Column("kunde", sa.String(length=255), nullable=True),
        sa.Column("fremdnr", sa.String(length=64), nullable=True),
        sa.Column("pos_typ_2", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=8), nullable=True),
        sa.Column("gesperrt", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "prio_liste",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("typ", sa.String(length=32), nullable=False),
        sa.Column("stand", sa.Date(), nullable=False),
        sa.Column("dateiname", sa.String(length=255), nullable=True),
        sa.Column("importiert_am", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "prio_liste_eintrag",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("liste_id", sa.Integer(), sa.ForeignKey("prio_liste.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vorgang_nr", sa.String(length=32), nullable=False),
        sa.Column("pos", sa.Integer(), nullable=False),
        sa.Column("upos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rang", sa.Integer(), nullable=True),
        sa.Column("termin", sa.Date(), nullable=True),
        sa.Column("kommentar", sa.Text(), nullable=True),
        sa.Column("extern_ref", sa.String(length=64), nullable=True),
        sa.UniqueConstraint("liste_id", "vorgang_nr", "pos", "upos", name="uq_prio_liste_eintrag"),
    )
    op.create_table(
        "prio_manuell",
        sa.Column("vorgang_nr", sa.String(length=32), primary_key=True),
        sa.Column("reihenfolge", sa.Integer(), nullable=False),
    )
    op.create_table(
        "prio_import",
        sa.Column("quelle", sa.String(length=32), primary_key=True),
        sa.Column("dateiname", sa.String(length=255), nullable=True),
        sa.Column("zeilen", sa.Integer(), nullable=False),
        sa.Column("warnungen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("importiert_am", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("prio_import")
    op.drop_table("prio_manuell")
    op.drop_table("prio_liste_eintrag")
    op.drop_table("prio_liste")
    op.drop_table("prio_auftrag_position")
    op.drop_index("ix_prio_plan_position_artikel", table_name="prio_plan_position")
    op.drop_table("prio_plan_position")
    op.drop_table("prio_artikel")
