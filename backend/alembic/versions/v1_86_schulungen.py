"""v1.86: Schulungen — Katalog, Teilnahmen, Import-Protokoll

Erste Stufe des Schulungs-/Onboarding-Moduls. Bildet die bisherige
``Schulungsübersicht.xlsx`` ab, die pro Bereich (betrieblich gesamt,
Produktion, Verwaltung) eine transponierte Matrix führt: Spalten sind
Mitarbeiter, Zeilen sind Schulungen mit je drei Werten (Initial / aktuell /
nächste Fälligkeit).

Bewusste Entscheidungen:

* ``schulung_teilnahme.employee_id`` ist NULLABLE. Die Excel identifiziert
  Mitarbeiter über die Personalnummer, die in Personio nur bei einem Teil der
  Belegschaft gepflegt ist. Nicht zuordenbare Zeilen gehen deshalb nicht
  verloren, sondern behalten ``personalnummer`` + ``mitarbeiter_name`` und
  können später nachgezogen werden.
* ``turnus`` bleibt als Originaltext erhalten; ``turnus_monate`` ist die daraus
  abgeleitete, rechenbare Periode. Für "bei Bedarf" und "alle 3 - 5 Jahre"
  bleibt sie NULL — daraus lässt sich keine Fälligkeit berechnen, und ein
  erfundener Wert wäre schlimmer als keiner.
* ``naechste_faellig`` speichert die Quartalsangabe der Excel ("Q3/2025")
  unverändert; ``naechste_faellig_am`` ist das berechnete Datum, sofern
  ``turnus_monate`` bekannt ist.
"""
import sqlalchemy as sa

from alembic import op

revision = "v1_86_schulungen"
down_revision = "v1_85_audit_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schulung_katalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bereich", sa.String(50), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("turnus", sa.String(80), nullable=True),
        sa.Column("turnus_monate", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("aktiv", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("bereich", "name", name="uq_schulung_katalog_bereich_name"),
    )
    op.create_index("ix_schulung_katalog_bereich", "schulung_katalog", ["bereich"])

    op.create_table(
        "schulung_import",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dateiname", sa.Text(), nullable=False),
        sa.Column(
            "importiert_am",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("schulungen_gesamt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("teilnahmen_gesamt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("nicht_zugeordnet", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notiz", sa.Text(), nullable=True),
    )

    op.create_table(
        "schulung_teilnahme",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "schulung_id",
            sa.Integer(),
            sa.ForeignKey("schulung_katalog.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Nullable: Excel-Zeilen ohne Personio-Treffer bleiben erhalten.
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("personio_employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("personalnummer", sa.String(30), nullable=False),
        sa.Column("mitarbeiter_name", sa.Text(), nullable=True),
        sa.Column("abteilung_kuerzel", sa.String(30), nullable=True),
        sa.Column("initial_datum", sa.Date(), nullable=True),
        sa.Column("aktuell_datum", sa.Date(), nullable=True),
        sa.Column("naechste_faellig", sa.String(30), nullable=True),
        sa.Column("naechste_faellig_am", sa.Date(), nullable=True),
        sa.Column(
            "import_id",
            sa.Integer(),
            sa.ForeignKey("schulung_import.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "schulung_id", "personalnummer", name="uq_schulung_teilnahme_schulung_persnr"
        ),
    )
    op.create_index(
        "ix_schulung_teilnahme_employee", "schulung_teilnahme", ["employee_id"]
    )
    op.create_index(
        "ix_schulung_teilnahme_persnr", "schulung_teilnahme", ["personalnummer"]
    )


def downgrade() -> None:
    op.drop_index("ix_schulung_teilnahme_persnr", table_name="schulung_teilnahme")
    op.drop_index("ix_schulung_teilnahme_employee", table_name="schulung_teilnahme")
    op.drop_table("schulung_teilnahme")
    op.drop_table("schulung_import")
    op.drop_index("ix_schulung_katalog_bereich", table_name="schulung_katalog")
    op.drop_table("schulung_katalog")
