"""v1.89: Teilnahme auch ohne Personalnummer — Personio-ID als Schlüssel

Die Personalnummer stammt aus der Schulungs-Excel und ist in Personio nur bei
einem Teil der Belegschaft gepflegt (24 von 71 aktiven). Für neu angelegte
Mitarbeiter existiert sie oft gar nicht — die Auto-Anlage eines Schulungsplans
scheiterte dadurch für die Mehrheit.

Der stabile Schlüssel ist die Personio-ID (``employee_id``), wie es auch das
Prozesskonzept vorsieht ("Personio-Personenschlüssel"). Deshalb:

* ``personalnummer`` wird NULLABLE — sie bleibt der Schlüssel für die
  historischen Excel-Zeilen, ist aber nicht mehr Pflicht.
* Statt einer gemeinsamen UNIQUE-Bedingung gibt es zwei **partielle** Indizes,
  je einen pro Identitätsart. So kann keine Dublette entstehen, egal über
  welchen Schlüssel eine Zeile angelegt wurde.
"""
import sqlalchemy as sa

from alembic import op

revision = "v1_89_teilnahme_employee_key"
down_revision = "v1_88_schulung_rolle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_schulung_teilnahme_schulung_persnr", "schulung_teilnahme", type_="unique"
    )
    op.alter_column("schulung_teilnahme", "personalnummer", nullable=True)

    # Je Identitätsart ein partieller Unique-Index.
    op.create_index(
        "uq_schulung_teilnahme_persnr",
        "schulung_teilnahme",
        ["schulung_id", "personalnummer"],
        unique=True,
        postgresql_where=sa.text("personalnummer IS NOT NULL"),
    )
    op.create_index(
        "uq_schulung_teilnahme_employee",
        "schulung_teilnahme",
        ["schulung_id", "employee_id"],
        unique=True,
        postgresql_where=sa.text("employee_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_schulung_teilnahme_employee", table_name="schulung_teilnahme")
    op.drop_index("uq_schulung_teilnahme_persnr", table_name="schulung_teilnahme")
    # Zeilen ohne Personalnummer würden die alte Bedingung verletzen.
    op.execute("DELETE FROM schulung_teilnahme WHERE personalnummer IS NULL")
    op.alter_column("schulung_teilnahme", "personalnummer", nullable=False)
    op.create_unique_constraint(
        "uq_schulung_teilnahme_schulung_persnr",
        "schulung_teilnahme",
        ["schulung_id", "personalnummer"],
    )
