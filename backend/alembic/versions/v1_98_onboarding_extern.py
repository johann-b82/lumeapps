"""v1.98: manuell gepflegte Onboarding-Einträge (nicht in Personio).

Personen, die (noch) nicht in Personio stehen, aber im Onboarding auftauchen
sollen — mit Markierung, abteilungsbasiertem Plan und Dokument-Downloads. Im API
laufen sie über eine negative employee_id.

Revision ID: v1_98_onboarding_extern
Revises: v1_97_onboarding_paket_download
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_98_onboarding_extern"
down_revision = "v1_97_onboarding_paket_download"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "onboarding_extern",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("abteilung", sa.Text(), nullable=True),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=True),
        sa.Column("paket_heruntergeladen_am", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "angelegt_am",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("onboarding_extern")
