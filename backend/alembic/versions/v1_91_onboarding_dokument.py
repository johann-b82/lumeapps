"""v1.91: Automatisch erzeugte Schulungsübersicht je Mitarbeiter.

Hält fest, welche Übersicht für wen erzeugt wurde und auf welchem Planstand sie
beruht. ``plan_signatur`` ist ein Hash über die Menge der Soll-Schulungen: ändert
sich die Anforderungsmatrix, weicht die Signatur ab und das Dokument wird beim
nächsten Abgleich neu erzeugt.

Revision ID: v1_91_onboarding_dokument
Revises: v1_90_kompetenzen
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_91_onboarding_dokument"
down_revision = "v1_90_kompetenzen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "onboarding_dokument",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("personio_employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("directus_file_uuid", sa.String(64), nullable=False),
        sa.Column("dateiname", sa.Text(), nullable=False),
        # Hash über die Soll-Schulungen; erkennt einen veralteten Stand.
        sa.Column("plan_signatur", sa.String(64), nullable=False),
        sa.Column("schulungen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "erzeugt_am",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Eine gültige Übersicht je Mitarbeiter — ältere werden beim Neuerzeugen
    # ersetzt, nicht angehäuft.
    op.create_index(
        "uq_onboarding_dokument_employee",
        "onboarding_dokument",
        ["employee_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_onboarding_dokument_employee", table_name="onboarding_dokument")
    op.drop_table("onboarding_dokument")
