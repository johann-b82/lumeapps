"""v1.90: Kompetenzen — Qualifikationsmatrix je Bereich.

Die Excel-Matrizen sind transponiert: Zeilen sind Qualifikationen, Spalten
sind Personen — je Person ein Spaltenpaar (Anforderungslevel, Erfüllungsgrad).
Das Schema bildet genau das ab.

``anzahl_mitarbeiter`` und ``durchschnitt`` stehen zwar in der Excel, werden
aber nicht gespeichert: beide sind aus den Bewertungen ableitbar, und zwei
Wahrheiten für dieselbe Zahl gehen irgendwann auseinander.

Revision ID: v1_90_kompetenzen
Revises: v1_89_teilnahme_employee_key
"""
from alembic import op
import sqlalchemy as sa

revision = "v1_90_kompetenzen"
down_revision = "v1_89_teilnahme_employee_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kompetenz_matrix",
        sa.Column("id", sa.Integer(), primary_key=True),
        # "produktion" | "verwaltung" | "safety" | "quality"
        sa.Column("bereich", sa.String(30), nullable=False),
        # Blattname der Datei — Quality bringt drei (QM, CS, QS) mit.
        sa.Column("blatt", sa.String(120), nullable=False),
        sa.Column("titel", sa.Text(), nullable=True),
        #: "Stand"-Datum aus der Kopfzeile der Excel.
        sa.Column("stand", sa.Date(), nullable=True),
        sa.Column("dateiname", sa.Text(), nullable=False),
        sa.Column(
            "importiert_am",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("bereich", "blatt", name="uq_kompetenz_matrix"),
    )

    op.create_table(
        "kompetenz_qualifikation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "matrix_id",
            sa.Integer(),
            sa.ForeignKey("kompetenz_matrix.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nr", sa.Integer(), nullable=True),
        sa.Column("kategorie", sa.Text(), nullable=True),
        sa.Column("bezeichnung", sa.Text(), nullable=False),
        #: Zeilenreihenfolge der Excel — die Fachbereiche lesen die Matrix so.
        sa.Column("reihenfolge", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_kompetenz_qualifikation_matrix", "kompetenz_qualifikation", ["matrix_id"]
    )

    op.create_table(
        "kompetenz_person",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "matrix_id",
            sa.Integer(),
            sa.ForeignKey("kompetenz_matrix.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        #: Treffer in Personio; NULL wenn der Name dort nicht auffindbar ist
        #: (Schreibfehler, Namenskürzel, oder eine reine "N/A"-Platzhalterspalte).
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("personio_employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reihenfolge", sa.Integer(), nullable=False),
    )
    op.create_index("ix_kompetenz_person_matrix", "kompetenz_person", ["matrix_id"])

    op.create_table(
        "kompetenz_bewertung",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "qualifikation_id",
            sa.Integer(),
            sa.ForeignKey("kompetenz_qualifikation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id",
            sa.Integer(),
            sa.ForeignKey("kompetenz_person.id", ondelete="CASCADE"),
            nullable=False,
        ),
        #: Anforderungslevel 0-4 (0 = nicht gefordert). Legende siehe Excel.
        sa.Column("anforderungslevel", sa.Integer(), nullable=True),
        #: Erfüllungsgrad 0-100 %.
        sa.Column("erfuellungsgrad", sa.Integer(), nullable=True),
        sa.UniqueConstraint("qualifikation_id", "person_id", name="uq_kompetenz_bewertung"),
    )


def downgrade() -> None:
    op.drop_table("kompetenz_bewertung")
    op.drop_index("ix_kompetenz_person_matrix", table_name="kompetenz_person")
    op.drop_table("kompetenz_person")
    op.drop_index("ix_kompetenz_qualifikation_matrix", table_name="kompetenz_qualifikation")
    op.drop_table("kompetenz_qualifikation")
    op.drop_table("kompetenz_matrix")
