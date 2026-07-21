"""v1.87: Anforderungsmatrix — welche Schulung ist für welche Abteilung Pflicht

Eine Regel je Kombination (Schulung, Ebene, Abteilung). Zwei Ebenen, weil beide
gebraucht werden:

* ``kuerzel``  — die feinen Abteilungskürzel der Schulungs-Excel (NÄH, WVK, CUT,
  MON …). Fachlich genau: Näherei und Zuschnitt haben unterschiedliche
  Pflichtschulungen.
* ``personio`` — die groben Personio-Abteilungen (Production, Human Resources …)
  für übergreifende Pflichten wie Sicherheitsunterweisung oder Erste Hilfe, die
  wirklich alle einer Abteilung betreffen.

Die Abteilung wird bewusst als Text geführt und NICHT als Fremdschlüssel: beide
Wertelisten stammen aus Fremdsystemen (Excel bzw. Personio) und es gibt keine
Abteilungstabelle, die man referenzieren könnte. Ein Wert, der dort verschwindet,
soll die Regel nicht löschen, sondern sichtbar verwaist zurücklassen.
"""
import sqlalchemy as sa

from alembic import op

revision = "v1_87_schulung_pflicht"
down_revision = "v1_86_schulungen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schulung_pflicht",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "schulung_id",
            sa.Integer(),
            sa.ForeignKey("schulung_katalog.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ebene", sa.String(20), nullable=False),
        sa.Column("abteilung", sa.String(80), nullable=False),
        sa.CheckConstraint("ebene IN ('kuerzel','personio')", name="ck_schulung_pflicht_ebene"),
        sa.UniqueConstraint(
            "schulung_id", "ebene", "abteilung", name="uq_schulung_pflicht_regel"
        ),
    )
    op.create_index(
        "ix_schulung_pflicht_ebene_abt", "schulung_pflicht", ["ebene", "abteilung"]
    )


def downgrade() -> None:
    op.drop_index("ix_schulung_pflicht_ebene_abt", table_name="schulung_pflicht")
    op.drop_table("schulung_pflicht")
