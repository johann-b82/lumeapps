"""v1.122: Schulungsvorgang trägt die geordnete Schulungsliste (Name + Trainer).

Damit sind (a) das Zuordnungs-Dropdown beim Zertifikat-Upload und (b) das je
Schulung vorausgefüllte Fbl.-68-Nachweisformular stabil an einen Index gebunden —
der QR auf dem Fbl. 68 kodiert ``{doc_uid}#{index}``, sodass der eingescannte
Nachweis automatisch der richtigen Schulung zugeordnet wird.

Revision ID: v1_122_schulung_nachweise
Revises: v1_121_schulung_vorgang
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "v1_122_schulung_nachweise"
down_revision = "v1_121_schulung_vorgang"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schulung_dokument", sa.Column("schulungen", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("schulung_dokument", "schulungen")
