"""v1.46: add upload_batches.kind to differentiate import types

Adds a `kind` discriminator column to upload_batches so the upload history
table can show what was imported (orders, contacts, …) and any future import
type can write to the same audit log.

Existing rows are backfilled to 'orders' since that was the only writer
before this revision.
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_46_upload_batch_kind"
down_revision = "v1_44_sales_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "upload_batches",
        sa.Column(
            "kind",
            sa.String(length=20),
            nullable=False,
            server_default="orders",
        ),
    )
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.drop_column("upload_batches", "kind")
