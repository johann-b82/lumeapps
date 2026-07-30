"""v1.96: app-seitiger Abteilungs-Override je Mitarbeiter.

Personio ist read-only; manche Mitarbeiter haben dort keine Abteilung. Diese
Tabelle hält eine in der App gesetzte Abteilung, die den Personio-Wert bei der
Onboarding-Plan-Berechnung ersetzt. Eine Zeile je Mitarbeiter (unique).

Revision ID: v1_96_onboarding_abteilung
Revises: v1_95_kompetenz_kategorie
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_96_onboarding_abteilung"
down_revision = "v1_95_kompetenz_kategorie"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "onboarding_abteilung",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("abteilung", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["personio_employees.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("employee_id", name="uq_onboarding_abteilung_employee"),
    )


def downgrade() -> None:
    op.drop_table("onboarding_abteilung")
