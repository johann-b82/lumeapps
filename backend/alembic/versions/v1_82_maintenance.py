"""v1.82: Maschinen-Wartung — machines + maintenance_tasks + maintenance_files

Three additive tables for the machine-maintenance module. Chains onto the
current head (v1_81_inspection_rsc); creates new tables only and touches no
existing data.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v1_82_maintenance"
down_revision = "v1_81_inspection_rsc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "machines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("inventory_no", sa.String(length=64), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("responsible", sa.String(length=255), nullable=True),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="active"
        ),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('active','inactive')", name="ck_machines_status"
        ),
    )

    op.create_table(
        "maintenance_tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "machine_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("machines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("interval_type", sa.String(length=16), nullable=False),
        sa.Column("interval_weeks", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "interval_type IN ('daily','weekly','monthly','quarterly','interval_weeks')",
            name="ck_maintenance_tasks_interval_type",
        ),
        sa.CheckConstraint(
            "interval_type <> 'interval_weeks' "
            "OR (interval_weeks IS NOT NULL AND interval_weeks >= 1)",
            name="ck_maintenance_tasks_interval_weeks",
        ),
    )
    op.create_index(
        "ix_maintenance_tasks_machine", "maintenance_tasks", ["machine_id"]
    )

    op.create_table(
        "maintenance_files",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "machine_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("machines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("directus_file_uuid", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=127), nullable=True),
        sa.Column(
            "file_kind", sa.String(length=16), nullable=False, server_default="plan"
        ),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "file_kind IN ('plan','archive')", name="ck_maintenance_files_file_kind"
        ),
    )
    op.create_index(
        "ix_maintenance_files_machine", "maintenance_files", ["machine_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_maintenance_files_machine", table_name="maintenance_files")
    op.drop_table("maintenance_files")
    op.drop_index("ix_maintenance_tasks_machine", table_name="maintenance_tasks")
    op.drop_table("maintenance_tasks")
    op.drop_table("machines")
