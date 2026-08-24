"""v1.111: Anwesenheits-ID auf String (Personio V2 liefert UUIDs).

Der Sync wechselt von V1 ``/company/attendances`` (Integer-IDs, 422 bei
mehrtägigen Perioden) auf V2 ``/v2/attendance-periods`` (UUID-IDs). Die
Anwesenheiten sind reine Cache-Daten und werden aus V2 vollständig neu
befüllt — daher wird die Tabelle geleert und der PK-Typ auf String geändert.

Revision ID: v1_111_attendance_v2_id
Revises: v1_110_zeugnis
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_111_attendance_v2_id"
down_revision = "v1_110_zeugnis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alte V1-Zeilen (Integer-IDs) verwerfen — V2 liefert die volle Historie neu.
    op.execute("TRUNCATE TABLE personio_attendance")
    op.alter_column(
        "personio_attendance",
        "id",
        existing_type=sa.Integer(),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute("TRUNCATE TABLE personio_attendance")
    op.alter_column(
        "personio_attendance",
        "id",
        existing_type=sa.String(length=64),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="id::integer",
    )
