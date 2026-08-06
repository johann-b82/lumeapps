"""v1.104: Kompetenz-Person kann auf einen Externen verweisen.

``kompetenz_person.extern_id`` verknüpft eine Matrix-Spalte optional mit
``onboarding_extern`` — so lassen sich Nicht-Personio-Personen (Leiharbeit,
externe Prüfer) über die Externe-Liste ergänzen statt als Freitext.

Revision ID: v1_104_kompetenz_extern
Revises: v1_103_einarbeitung_bereich
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_104_kompetenz_extern"
down_revision = "v1_103_einarbeitung_bereich"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kompetenz_person", sa.Column("extern_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_kompetenz_person_extern",
        "kompetenz_person",
        "onboarding_extern",
        ["extern_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_kompetenz_person_extern", "kompetenz_person", ["extern_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_kompetenz_person_extern", table_name="kompetenz_person")
    op.drop_constraint(
        "fk_kompetenz_person_extern", "kompetenz_person", type_="foreignkey"
    )
    op.drop_column("kompetenz_person", "extern_id")
