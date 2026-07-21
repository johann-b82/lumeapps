"""v1.85: Audit-Modul — Mehrfachkategorien je Audit

Replaces the single ``audits.category`` column with an ``audit_category_links``
join table, so one audit can be both a Prozessaudit and a Produktaudit at the
same time. The internal audit programme drives this: every audit there is a
"Part 1 Process Audit", and five of them are additionally a "Part 2 Product
Audit" — a single-valued column cannot express that without losing one half.

The backfill below copies each existing ``category`` into the join table before
the column is dropped, so the change is lossless even if rows exist. (At the
time of writing the production ``audits`` table is empty; the backfill is there
so the migration is correct wherever it runs.)
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "v1_85_audit_categories"
down_revision = "v1_84_audit"
branch_labels = None
depends_on = None

AUDIT_CATEGORIES = ("system", "prozess", "produkt", "lieferant")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({','.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "audit_category_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "audit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            _in_list("category", AUDIT_CATEGORIES),
            name="ck_audit_category_links_category",
        ),
        sa.UniqueConstraint("audit_id", "category", name="uq_audit_category_links"),
    )
    op.create_index(
        "ix_audit_category_links_audit", "audit_category_links", ["audit_id"]
    )

    # Lossless backfill before the source column goes away.
    op.execute(
        "INSERT INTO audit_category_links (audit_id, category) "
        "SELECT id, category FROM audits"
    )

    op.drop_constraint("ck_audits_category", "audits", type_="check")
    op.drop_column("audits", "category")


def downgrade() -> None:
    # Restore the single-valued column, keeping one category per audit. Which
    # one is arbitrary when an audit carries several — that information cannot
    # survive the round trip, which is why this direction loses data.
    op.add_column("audits", sa.Column("category", sa.String(length=16), nullable=True))
    op.execute(
        "UPDATE audits SET category = ("
        "  SELECT category FROM audit_category_links l "
        "  WHERE l.audit_id = audits.id ORDER BY category LIMIT 1"
        ")"
    )
    op.execute("UPDATE audits SET category = 'prozess' WHERE category IS NULL")
    op.alter_column("audits", "category", nullable=False)
    op.create_check_constraint(
        "ck_audits_category", "audits", _in_list("category", AUDIT_CATEGORIES)
    )

    op.drop_index("ix_audit_category_links_audit", table_name="audit_category_links")
    op.drop_table("audit_category_links")
