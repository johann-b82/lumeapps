"""v1.112: Newsletter — Ausgabe (Jahr/Quartal) + Einträge je Rubrik.

Revision ID: v1_112_newsletter
Revises: v1_111_attendance_v2_id
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_112_newsletter"
down_revision = "v1_111_attendance_v2_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "newsletter",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jahr", sa.Integer(), nullable=False),
        sa.Column("quartal", sa.Integer(), nullable=False),
        sa.Column("titel", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="entwurf"),
        sa.Column("erstellt_am", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aktualisiert_am", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("jahr", "quartal", name="uq_newsletter_ausgabe"),
    )
    op.create_table(
        "newsletter_eintrag",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("newsletter_id", sa.Integer(), nullable=False),
        sa.Column("rubrik", sa.String(length=20), nullable=False),
        sa.Column("untertitel", sa.Text(), nullable=False),
        sa.Column("inhalt_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("bild_data", sa.LargeBinary(), nullable=True),
        sa.Column("bild_mime", sa.String(length=64), nullable=True),
        sa.Column("reihenfolge", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["newsletter_id"], ["newsletter.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_newsletter_eintrag_newsletter", "newsletter_eintrag", ["newsletter_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_newsletter_eintrag_newsletter", table_name="newsletter_eintrag")
    op.drop_table("newsletter_eintrag")
    op.drop_table("newsletter")
