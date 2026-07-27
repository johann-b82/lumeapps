"""v1.95: deklarierte Kategorien je Kompetenzmatrix.

Erlaubt es, eine Kategorie zuerst leer anzulegen und danach mit Qualifikationen
zu füllen. Die Kategorie bleibt zusätzlich Freitext an der Qualifikation (die
Gruppierung); diese Tabelle hält den Namen auch ohne zugeordnete Qualifikation.
Additiv — bestehende Kategorien leiten sich weiterhin aus den Qualifikationen ab,
daher kein Backfill nötig.

Revision ID: v1_95_kompetenz_kategorie
Revises: v1_94_schulung_verantwortlicher
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_95_kompetenz_kategorie"
down_revision = "v1_94_schulung_verantwortlicher"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kompetenz_kategorie",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("matrix_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("reihenfolge", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["matrix_id"], ["kompetenz_matrix.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("matrix_id", "name", name="uq_kompetenz_kategorie"),
    )


def downgrade() -> None:
    op.drop_table("kompetenz_kategorie")
