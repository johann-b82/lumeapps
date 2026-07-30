"""v1.97: Vermerk über heruntergeladenes Onboarding-Paket.

Je Mitarbeiter ein Vermerk mit Zeitstempel, sobald sein Onboarding-Paket als PDF
heruntergeladen wurde. Steuert die „neu"-Markierung: solange kein Vermerk und der
Eintritt im Neu-Fenster liegt, gilt die Person als neu.

Revision ID: v1_97_onboarding_paket_download
Revises: v1_96_onboarding_abteilung
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_97_onboarding_paket_download"
down_revision = "v1_96_onboarding_abteilung"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "onboarding_paket_download",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column(
            "heruntergeladen_am",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["personio_employees.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("employee_id", name="uq_onboarding_paket_download_employee"),
    )


def downgrade() -> None:
    op.drop_table("onboarding_paket_download")
