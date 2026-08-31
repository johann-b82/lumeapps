"""v1.124: Zeugnis-Aussteller — HR-Manager als Personio-Person.

Fügt ``zeugnis_aussteller.hr_employee_id`` hinzu: die 2. Unterschrift (HR) wird
— wie der/die Vorgesetzte — LIVE aus Personio aufgelöst. NULL fällt auf die
bisherigen Freitextfelder ``unterzeichner2`` zurück.

Revision ID: v1_124_zeugnis_aussteller_hr
Revises: v1_123_zeugnis_baustein
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_124_zeugnis_aussteller_hr"
down_revision = "v1_123_zeugnis_baustein"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "zeugnis_aussteller",
        sa.Column("hr_employee_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_zeugnis_aussteller_hr_employee",
        "zeugnis_aussteller",
        "personio_employees",
        ["hr_employee_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_zeugnis_aussteller_hr_employee", "zeugnis_aussteller", type_="foreignkey"
    )
    op.drop_column("zeugnis_aussteller", "hr_employee_id")
