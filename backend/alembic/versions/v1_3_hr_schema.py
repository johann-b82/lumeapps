"""v1.3 HR schema: Personio tables and AppSettings credential columns

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-12
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import BYTEA, JSONB

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- personio_employees --------------------------------------------------
    op.create_table(
        "personio_employees",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("position", sa.String(255), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("weekly_working_hours", sa.Numeric(5, 2), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_json", JSONB(), nullable=True),
    )

    # --- personio_attendance -------------------------------------------------
    op.create_table(
        "personio_attendance",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("personio_employees.id"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_holiday", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_json", JSONB(), nullable=True),
    )

    # --- personio_absences ---------------------------------------------------
    op.create_table(
        "personio_absences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("personio_employees.id"),
            nullable=False,
        ),
        sa.Column("absence_type_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("time_unit", sa.String(10), nullable=False),
        sa.Column("hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_json", JSONB(), nullable=True),
    )

    # --- personio_sync_meta --------------------------------------------------
    op.create_table(
        "personio_sync_meta",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(20), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("employees_synced", sa.Integer(), nullable=True),
        sa.Column("attendance_synced", sa.Integer(), nullable=True),
        sa.Column("absences_synced", sa.Integer(), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_personio_sync_meta_singleton"),
    )

    # --- Indexes -------------------------------------------------------------
    op.create_index(
        "ix_personio_attendance_employee_date",
        "personio_attendance",
        ["employee_id", "date"],
    )
    op.create_index(
        "ix_personio_absences_employee_start_type",
        "personio_absences",
        ["employee_id", "start_date", "absence_type_id"],
    )

    # --- AppSettings credential columns --------------------------------------
    op.add_column(
        "app_settings",
        sa.Column("personio_client_id_enc", BYTEA(), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("personio_client_secret_enc", BYTEA(), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "personio_sync_interval_h",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )

    # --- Seed personio_sync_meta singleton row -------------------------------
    op.execute("INSERT INTO personio_sync_meta (id) VALUES (1)")


def downgrade() -> None:
    # Reverse in reverse order
    op.drop_column("app_settings", "personio_sync_interval_h")
    op.drop_column("app_settings", "personio_client_secret_enc")
    op.drop_column("app_settings", "personio_client_id_enc")

    op.drop_index("ix_personio_absences_employee_start_type", table_name="personio_absences")
    op.drop_index("ix_personio_attendance_employee_date", table_name="personio_attendance")

    op.drop_table("personio_sync_meta")
    op.drop_table("personio_absences")
    op.drop_table("personio_attendance")
    op.drop_table("personio_employees")
