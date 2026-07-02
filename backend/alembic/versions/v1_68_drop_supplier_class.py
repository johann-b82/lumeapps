"""v1.68: Drop supplier_classifications (dead code from v1.67 planning)

The Lieferanten- and Unterauftragnehmer-Reklamationsquoten ended up using
the WGR (Warengruppe) column on ``goods_receipt_records`` directly — see
``FMD_WGR_CODES`` in app/services/complaint_rate_aggregation.py. The
``supplier_classifications`` table was a leftover from the original plan
to JOIN against a dev_excel_LIE Klasse-1 export; never populated.

Removes the table and the ``'supplier_classes'`` value from the
``ck_upload_batches_kind`` check constraint.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "v1_68_drop_supplier_class"
down_revision = "v1_67_goods_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        "ix_supplier_classifications_klasse_1",
        table_name="supplier_classifications",
    )
    op.drop_table("supplier_classifications")

    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers',"
        "'revenues','auftraege','deliveries','delivery_reliability',"
        "'tippspiel','goods_receipts')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers',"
        "'revenues','auftraege','deliveries','delivery_reliability',"
        "'tippspiel','goods_receipts','supplier_classes')",
    )

    op.create_table(
        "supplier_classifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "upload_batch_id",
            sa.Integer(),
            sa.ForeignKey("upload_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("supplier_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("supplier_name", sa.String(length=255), nullable=True),
        sa.Column("klasse_1", sa.String(length=50), nullable=True),
        sa.Column("klasse_2", sa.String(length=50), nullable=True),
        sa.Column("raw", JSONB(), nullable=True),
    )
    op.create_index(
        "ix_supplier_classifications_klasse_1",
        "supplier_classifications",
        ["klasse_1"],
    )
