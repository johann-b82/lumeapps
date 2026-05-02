from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    BigInteger as sa_BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "success" | "failed" | "partial"

    records: Mapped[list["SalesRecord"]] = relationship(
        "SalesRecord",
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class SalesRecord(Base):
    __tablename__ = "sales_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="CASCADE"),
        nullable=False,
    )

    # --- Business key ---
    order_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    # --- String columns ---
    erp_status_flag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    order_subtype: Mapped[str | None] = mapped_column(String(50), nullable=True)
    complexity_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    vv_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    business_area: Mapped[str | None] = mapped_column(Integer, nullable=True)
    project_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manual_lock: Mapped[str | None] = mapped_column(String(10), nullable=True)
    responsible_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    free_field_1: Mapped[str | None] = mapped_column(String(10), nullable=True)
    free_field_2: Mapped[str | None] = mapped_column(String(10), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manual_status: Mapped[str | None] = mapped_column(Integer, nullable=True)
    customer_lock: Mapped[str | None] = mapped_column(Integer, nullable=True)
    material_flag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    end_customer_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_processor_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    internal_processor_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approval_comment_1: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[str | None] = mapped_column(Integer, nullable=True)
    technical_check: Mapped[str | None] = mapped_column(String(10), nullable=True)
    purchase_check: Mapped[str | None] = mapped_column(String(10), nullable=True)
    approval_comment_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    # v1.44: ERP "Benutzer" — token of the user who created the order. Used as
    # the rep field for orders/wk/rep, replacing the Kontakte bridge. Nullable
    # because legacy rows uploaded before v1.44 won't have it.
    created_by_user: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- Date columns (per D-10: nullable, DD.MM.YYYY) ---
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    requested_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    arrival_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Decimal columns (per D-04: NUMERIC exact, nullable) ---
    remaining_value: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    total_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    batch: Mapped["UploadBatch"] = relationship(
        "UploadBatch",
        back_populates="records",
    )


class AppSettings(Base):
    """Singleton settings row — exactly one row with id=1, enforced by CHECK constraint.

    Per D-01 / D-02: logo bytes live on the same row (no separate app_logos table).
    """
    __tablename__ = "app_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_app_settings_singleton"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=False
    )

    # Colors — oklch strings, validated at the Pydantic layer (see schemas.py)
    color_primary: Mapped[str] = mapped_column(String(64), nullable=False)
    color_accent: Mapped[str] = mapped_column(String(64), nullable=False)
    color_background: Mapped[str] = mapped_column(String(64), nullable=False)
    color_foreground: Mapped[str] = mapped_column(String(64), nullable=False)
    color_muted: Mapped[str] = mapped_column(String(64), nullable=False)
    color_destructive: Mapped[str] = mapped_column(String(64), nullable=False)

    # App identity
    app_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # v1.18 Phase 51 D-01: app-level timezone for signage schedule resolver.
    # Default 'Europe/Berlin' matches current DACH deployment target.
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="Europe/Berlin"
    )

    # Logo — all three are nullable together (no logo = fallback to app_name text)
    logo_data: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    logo_mime: Mapped[str | None] = mapped_column(String(64), nullable=True)
    logo_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Personio credentials — Fernet-encrypted BYTEA (D-01, D-04)
    personio_client_id_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    personio_client_secret_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)

    # Sync interval for APScheduler (Phase 13) — default 168h (weekly). A
    # weekly cadence is appropriate now that the Personio attendance fetch
    # does a full first-run backfill + incremental updates (Phase 60 follow-up).
    personio_sync_interval_h: Mapped[int] = mapped_column(Integer, nullable=False, default=168)

    # Personio KPI configuration columns — JSONB arrays (Phase 19)
    personio_sick_leave_type_id: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    personio_production_dept: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    personio_skill_attr_key: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # HR KPI target values — nullable (no target = no reference line)
    target_overtime_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    target_sick_leave_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    target_fluctuation: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    target_revenue_per_employee: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)

    # --- v1.15 Sensor Monitor (Phase 38) ---
    sensor_poll_interval_s: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60
    )
    sensor_temperature_min: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 3), nullable=True
    )
    sensor_temperature_max: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 3), nullable=True
    )
    sensor_humidity_min: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 3), nullable=True
    )
    sensor_humidity_max: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 3), nullable=True
    )


class PersonioEmployee(Base):
    __tablename__ = "personio_employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weekly_working_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    attendances: Mapped[list["PersonioAttendance"]] = relationship(
        "PersonioAttendance",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    absences: Mapped[list["PersonioAbsence"]] = relationship(
        "PersonioAbsence",
        back_populates="employee",
        cascade="all, delete-orphan",
    )


class PersonioAttendance(Base):
    __tablename__ = "personio_attendance"
    __table_args__ = (
        Index("ix_personio_attendance_employee_date", "employee_id", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("personio_employees.id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_holiday: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    employee: Mapped["PersonioEmployee"] = relationship(
        "PersonioEmployee",
        back_populates="attendances",
    )


class PersonioAbsence(Base):
    __tablename__ = "personio_absences"
    __table_args__ = (
        Index(
            "ix_personio_absences_employee_start_type",
            "employee_id",
            "start_date",
            "absence_type_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("personio_employees.id"), nullable=False
    )
    absence_type_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    time_unit: Mapped[str] = mapped_column(String(10), nullable=False)
    hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    employee: Mapped["PersonioEmployee"] = relationship(
        "PersonioEmployee",
        back_populates="absences",
    )


class PersonioSyncMeta(Base):
    __tablename__ = "personio_sync_meta"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_personio_sync_meta_singleton"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_sync_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    employees_synced: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attendance_synced: Mapped[int | None] = mapped_column(Integer, nullable=True)
    absences_synced: Mapped[int | None] = mapped_column(Integer, nullable=True)


# --- v1.15 Sensor models (Phase 38) ---


class Sensor(Base):
    """SNMP sensor configuration — one row per physical device.

    community is Fernet-ciphertext (BYTEA), never plaintext (PITFALLS C-3).
    Reuse app.security.sensor_community.encrypt_community / decrypt_community.
    """
    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=161)
    community: Mapped[bytes] = mapped_column(BYTEA, nullable=False)  # Fernet ciphertext
    temperature_oid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    humidity_oid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    temperature_scale: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("1.0")
    )
    humidity_scale: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("1.0")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # v1.39: optional `#rrggbb` chart color override; NULL → fall back to the
    # frontend palette index. Validated as 7-char hex by SensorCreate /
    # SensorUpdate; never stored as anything other than a 7-char string.
    chart_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    readings: Mapped[list["SensorReading"]] = relationship(
        "SensorReading",
        back_populates="sensor",
        cascade="all, delete-orphan",
    )
    poll_logs: Mapped[list["SensorPollLog"]] = relationship(
        "SensorPollLog",
        back_populates="sensor",
        cascade="all, delete-orphan",
    )


class SensorReading(Base):
    """One row per successful poll. Failed polls go to sensor_poll_log (PITFALLS M-4)."""
    __tablename__ = "sensor_readings"
    __table_args__ = (
        Index(
            "ix_sensor_readings_sensor_recorded_at_desc",
            "sensor_id",
            "recorded_at",
        ),
        # UNIQUE(sensor_id, recorded_at) prevents duplicate rows from scheduled+manual
        # poll collision (PITFALLS C-5). Use ON CONFLICT DO NOTHING on insert.
    )

    id: Mapped[int] = mapped_column(
        sa_BigInteger, primary_key=True, autoincrement=True
    )
    sensor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    humidity: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    sensor: Mapped["Sensor"] = relationship("Sensor", back_populates="readings")


class SensorPollLog(Base):
    """Liveness log — one row per poll attempt (success OR failure).

    Separates data (sensor_readings) from liveness (this table) per PITFALLS M-4.
    Lets the UI render 'Offline seit X min' without scanning the readings dataset.
    """
    __tablename__ = "sensor_poll_log"
    __table_args__ = (
        Index(
            "ix_sensor_poll_log_sensor_attempted_at_desc",
            "sensor_id",
            "attempted_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        sa_BigInteger, primary_key=True, autoincrement=True
    )
    sensor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False
    )
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_kind: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sensor: Mapped["Sensor"] = relationship("Sensor", back_populates="poll_logs")


class SalesContact(Base):
    """Sales contact log row from the Kontakte ERP dump.

    One row per recorded contact event (call, email, on-site visit,
    inquiry, quote). KPI rules (Erstkontakte / Interessenten / Visits /
    Angebote) are applied at read time on ``status = 1`` rows only.
    """

    __tablename__ = "sales_contacts"
    __table_args__ = (
        Index("ix_sales_contacts_date", "contact_date"),
        Index("ix_sales_contacts_token", "employee_token"),
        CheckConstraint("status IN (0, 1)", name="sales_contacts_status_check"),
    )

    id: Mapped[int] = mapped_column(sa_BigInteger, primary_key=True, autoincrement=True)
    contact_date: Mapped[date] = mapped_column(Date, nullable=False)
    employee_token: Mapped[str] = mapped_column(String(128), nullable=False)
    contact_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# v1.41 introduced a SalesEmployeeAlias model that bound the Kontakte
# file's ``Wer`` token to a Personio employee. v1.42 removes the
# binding entirely — sales reps are identified directly by the token —
# so the model has been deleted along with the Alembic table drop.
