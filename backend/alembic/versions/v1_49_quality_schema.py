"""v1.49: Quality KPI schema — quality_records + extend upload_batches.kind

Adds a `quality_records` table for 8D-report rows ingested from the
"8D.txt" tab-separated dump. Each row is one 8D report (audit finding
or complaint). The Quality KPI dashboard filters this table by
`art` (audit type code: BH AUD / EX AUD / IN AUD / KU AUD) and counts
findings per `level` (1 = Major, 2 = Minor) over a date window.

Also extends `ck_upload_batches_kind` to permit `kind='quality'` so
the new POST /api/upload-quality endpoint can write its audit-log entry.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "v1_49_quality_schema"
down_revision = "v1_46_upload_batch_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. quality_records — one row per 8D report.
    #    report_nr is the business key from the 8D file's "Nr." column.
    #    We store it as a string to avoid surprises if the source ever
    #    decides to use alphanumeric IDs; ON CONFLICT idempotency relies
    #    on the UNIQUE index.
    op.create_table(
        "quality_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "upload_batch_id",
            sa.Integer(),
            sa.ForeignKey("upload_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_nr", sa.String(length=50), nullable=False, unique=True),
        sa.Column("report_date", sa.Date(), nullable=True),
        # art = audit-type code from column "Art" (e.g. BH AUD, EX AUD,
        # IN AUD, KU AUD). Stored verbatim — the KPI router filters by
        # exact match against the four codes listed above. NULL for the
        # later Reklamationen branch (when art is empty in the source).
        sa.Column("art", sa.String(length=20), nullable=True),
        # level = 1 (Major), 2 (Minor), or NULL when the source row's
        # "Artikel" string does not match either. NULL rows are still
        # ingested so future filters can re-classify without re-upload.
        sa.Column("level", sa.SmallInteger(), nullable=True),
        sa.Column("issuer", sa.String(length=255), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("customer_id", sa.String(length=50), nullable=True),
        sa.Column("designation", sa.Text(), nullable=True),
        sa.Column("status_code", sa.String(length=50), nullable=True),
        sa.Column("problem_description", sa.Text(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("raw", JSONB(), nullable=True),
        sa.CheckConstraint(
            "level IS NULL OR level IN (1, 2)",
            name="ck_quality_records_level",
        ),
    )
    op.create_index(
        "ix_quality_records_report_date",
        "quality_records",
        ["report_date"],
    )
    op.create_index(
        "ix_quality_records_art_level_date",
        "quality_records",
        ["art", "level", "report_date"],
    )

    # 2. Extend upload_batches.kind to permit 'quality'.
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts')",
    )
    op.drop_index("ix_quality_records_art_level_date", table_name="quality_records")
    op.drop_index("ix_quality_records_report_date", table_name="quality_records")
    op.drop_table("quality_records")
