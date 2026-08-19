"""v1.105: Seiten-Feedback — globales Bewertungs-/Problemmelde-Widget.

Neue Tabelle ``page_feedback``: jede eingeloggte Person kann von jeder
Intranet-Seite aus Feedback abgeben (Freitext + optionaler Screenshot der
aktuellen Ansicht). Der Screenshot liegt als ``bytea`` direkt in Postgres
(gleiches Muster wie ``app_settings.logo_data``) — self-contained, keine
Directus-Datei nötig. Gesichtet wird über eine admin-only Übersichtsseite.

Revision ID: v1_105_page_feedback
Revises: v1_104_kompetenz_extern
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import BYTEA, UUID

revision = "v1_105_page_feedback"
down_revision = "v1_104_kompetenz_extern"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_feedback",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Directus user id from the JWT (trusted). Nullable so a row survives
        # even if the token shape ever changes.
        sa.Column("created_by_id", UUID(as_uuid=True), nullable=True),
        # Client-supplied display hint (real email is not in the JWT).
        sa.Column("reporter_email", sa.String(320), nullable=True),
        sa.Column("page_url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("screenshot_data", BYTEA(), nullable=True),
        sa.Column("screenshot_mime", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("viewport", sa.String(32), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="new",
        ),
        sa.CheckConstraint(
            "status IN ('new','resolved')", name="ck_page_feedback_status"
        ),
    )
    op.create_index(
        "ix_page_feedback_created_at",
        "page_feedback",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_page_feedback_created_at", table_name="page_feedback")
    op.drop_table("page_feedback")
