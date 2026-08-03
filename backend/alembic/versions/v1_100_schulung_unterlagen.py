"""v1.100: Schulungsbeschreibung + Schulungsunterlagen.

``schulung_katalog.beschreibung`` (Freitext, wie Turnus/Frist je Name geteilt) und
``schulung_unterlage`` (hochgeladene Dateien in Directus, verknüpft über den
normalisierten Schulungs-Namen, damit sie bei allen gleichnamigen Schulungen
erscheinen).

Revision ID: v1_100_schulung_unterlagen
Revises: v1_99_einarbeitung_katalog
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_100_schulung_unterlagen"
down_revision = "v1_99_einarbeitung_katalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schulung_katalog", sa.Column("beschreibung", sa.Text(), nullable=True))
    op.create_table(
        "schulung_unterlage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name_norm", sa.String(length=255), nullable=False),
        sa.Column("directus_file_uuid", sa.String(length=64), nullable=False),
        sa.Column("dateiname", sa.Text(), nullable=False),
        sa.Column("mime", sa.String(length=127), nullable=True),
        sa.Column(
            "hochgeladen_am",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_schulung_unterlage_name", "schulung_unterlage", ["name_norm"]
    )


def downgrade() -> None:
    op.drop_index("ix_schulung_unterlage_name", table_name="schulung_unterlage")
    op.drop_table("schulung_unterlage")
    op.drop_column("schulung_katalog", "beschreibung")
