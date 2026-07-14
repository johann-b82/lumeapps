"""v1.79: inspection_records (AswQs2151 upload).

Table that backs the Qualitätsprüfung view — one row per inspection
booking from the AswQs2151.txt export. Fills the previously stubbed
:func:`app.services.inspection_aggregation.compute_inspections`.

The source has no clean business key (identical booking rows are
allowed, e.g. two 16-STK bookings same date/time/user), so idempotency
is the "delete-by-date-range then insert" pattern used by
``material_movements`` — re-uploading the same file is a no-op.

Also widens the ``upload_batches.ck_upload_batches_kind`` CHECK to
accept ``'inspections'`` so the new upload endpoint can log a batch.
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_79_inspection_records"
down_revision = "v1_78_inspection_targets"
branch_labels = None
depends_on = None


_KIND_VALUES_OLD = (
    "orders", "contacts", "quality", "interessenten", "offers",
    "revenues", "auftraege", "deliveries", "delivery_reliability",
    "tippspiel", "goods_receipts", "material_movements",
    "material_prices", "auftrag_positionen",
)
_KIND_VALUES_NEW = (*_KIND_VALUES_OLD, "inspections")


def _kind_check(values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{v}'" for v in values)
    return f"kind IN ({joined})"


def upgrade() -> None:
    op.create_table(
        "inspection_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "upload_batch_id",
            sa.Integer(),
            sa.ForeignKey("upload_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pruef_datum", sa.Date(), nullable=False),
        sa.Column("pruef_zeit", sa.Time(), nullable=True),
        sa.Column("benutzer", sa.String(64), nullable=True),
        sa.Column("fa", sa.String(50), nullable=True),
        sa.Column("artikel", sa.String(50), nullable=True),
        sa.Column("bezeichnung", sa.Text(), nullable=True),
        sa.Column("buchungs_menge", sa.Numeric(15, 3), nullable=True),
        sa.Column("ausschuss_menge", sa.Numeric(15, 3), nullable=True),
        sa.Column("produktgruppe", sa.String(64), nullable=True),
        sa.Column("typ", sa.String(10), nullable=True),
        # 'large' or 'small' — decided at parse time from bezeichnung/produktgruppe.
        sa.Column("size_class", sa.String(10), nullable=False),
        sa.Column(
            "raw", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.create_index(
        "ix_inspection_records_pruef_datum",
        "inspection_records",
        ["pruef_datum"],
    )
    op.create_index(
        "ix_inspection_records_size_class_datum",
        "inspection_records",
        ["size_class", "pruef_datum"],
    )
    op.create_check_constraint(
        "ck_inspection_records_size_class",
        "inspection_records",
        "size_class IN ('large', 'small')",
    )

    # Widen upload_batches.kind CHECK to accept the new 'inspections' kind.
    op.drop_constraint(
        "ck_upload_batches_kind", "upload_batches", type_="check"
    )
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        _kind_check(_KIND_VALUES_NEW),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_upload_batches_kind", "upload_batches", type_="check"
    )
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        _kind_check(_KIND_VALUES_OLD),
    )
    op.drop_constraint(
        "ck_inspection_records_size_class",
        "inspection_records",
        type_="check",
    )
    op.drop_index(
        "ix_inspection_records_size_class_datum",
        table_name="inspection_records",
    )
    op.drop_index(
        "ix_inspection_records_pruef_datum",
        table_name="inspection_records",
    )
    op.drop_table("inspection_records")
