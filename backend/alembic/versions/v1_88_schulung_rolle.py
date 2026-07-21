"""v1.88: Zuordnung Personio-Position -> Abteilungskürzel

Brücke für die Auto-Ableitung bei Neueintritten. Personio kennt nur die grobe
Abteilung ("Production"), die Anforderungsmatrix arbeitet auf der feinen Ebene
der Excel-Kürzel (NÄH, CUT, WVK …). Ohne diese Tabelle könnte für einen neuen
Mitarbeiter nur die grobe Ebene ausgewertet werden.

Die Position ist Freitext aus Personio und uneinheitlich gepflegt (fünf
Schreibweisen für "Produktionsmitarbeiter", zwei davon Tippfehler). Deshalb
wird auf einer normalisierten Form abgeglichen: klein geschrieben, Mehrfach-
Leerzeichen zusammengefasst. Die Originalschreibweise bleibt zur Anzeige
erhalten.
"""
import sqlalchemy as sa

from alembic import op

revision = "v1_88_schulung_rolle"
down_revision = "v1_87_schulung_pflicht"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schulung_rolle",
        sa.Column("id", sa.Integer(), primary_key=True),
        # Originalschreibweise, wie sie in Personio steht.
        sa.Column("position", sa.Text(), nullable=False),
        # Normalisiert (lower, Whitespace zusammengefasst) — darauf wird gematcht.
        sa.Column("position_norm", sa.String(200), nullable=False),
        # Ziel: Abteilungskürzel der Schulungs-Excel (NÄH, CUT, WVK …).
        sa.Column("abteilung_kuerzel", sa.String(30), nullable=False),
        sa.UniqueConstraint("position_norm", name="uq_schulung_rolle_position"),
    )
    op.create_index(
        "ix_schulung_rolle_kuerzel", "schulung_rolle", ["abteilung_kuerzel"]
    )


def downgrade() -> None:
    op.drop_index("ix_schulung_rolle_kuerzel", table_name="schulung_rolle")
    op.drop_table("schulung_rolle")
