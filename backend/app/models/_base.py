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
    UniqueConstraint,
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
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="orders"
    )  # "orders" | "contacts" — discriminator for the upload history view (v1.46)

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

    # v1.102 — Personio-Rückschreiben (INERT bis Freischaltung): Master-Schalter
    # (default aus) + Dokumentenkategorie-ID, in die Schulungs-/Kompetenznachweise
    # ins Personio-Mitarbeiterprofil hochgeladen werden. Braucht Personio-Schreib-
    # Scopes (Dokumente lesen+schreiben) — bis dahin bleibt der Push ein No-Op.
    personio_writeback_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    personio_writeback_kategorie_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # HR KPI target values — nullable (no target = no reference line)
    target_overtime_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    target_sick_leave_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    target_fluctuation: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    target_revenue_per_employee: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)

    # v1.60 — Quality KPI targets. Rates are stored as fractions (0.02 = 2 %);
    # finding counts are integers. NULL hides the chart's reference line.
    target_complaint_rate_customer: Mapped[float | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    target_complaint_rate_internal: Mapped[float | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    # v1.69: same pattern for the supplier (LIE RE) + subcontractor
    # (UA RE / Werkbänke) On-Quality target lines.
    target_complaint_rate_supplier: Mapped[float | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    target_complaint_rate_subcontractor: Mapped[float | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    target_audit_findings_level1: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    target_audit_findings_level2: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    # v1.70: Qualitätsprüfung — Produkte/Tag/Mitarbeiter targets.
    target_inspection_large: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    target_inspection_small: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # v1.71 / v1.72 — Finance KPI targets. Stored as fractions (0.15 = 15 %);
    # NULL hides the chart's reference line.
    target_material_cost_ratio: Mapped[float | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    target_personnel_cost_ratio: Mapped[float | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    # v1.77 — Produktion Verzug target (max Verzugsquote as fraction, 0.20 = 20 %);
    # NULL hides the chart's reference line.
    target_produktion_verzug: Mapped[float | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )

    # v1.55 — Sales-dashboard weekly target values (drive the dashed
    # reference lines on the Vertriebsaktivität card). NULL = "no target
    # set" — the frontend falls back to a baked-in default.
    target_sales_erstkontakte: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    target_sales_interessenten: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    target_sales_besuche: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    target_sales_angebote_eur: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    # v1.56 — €/week/rep goal for the OrdersDistributionCard headline tile.
    target_sales_orders_per_rep_eur: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)

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

    # v1.57 — World Cup signage embed (football-data.org). Key is
    # Fernet-encrypted like the Personio credentials above.
    worldcup_api_key_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    worldcup_refresh_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60
    )

    # --- v1.65 ATR fileserver (Phase C) ---
    atr_smb_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    atr_smb_share: Mapped[str | None] = mapped_column(String(255), nullable=True)
    atr_smb_domain: Mapped[str | None] = mapped_column(String(128), nullable=True)
    atr_smb_user: Mapped[str | None] = mapped_column(String(128), nullable=True)
    atr_smb_password_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    atr_input_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    atr_output_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    atr_archive_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    atr_scan_interval_s: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    atr_auto_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- v1.83 E-Mail background module — Office 365 / Microsoft Graph ---
    # Shared notification service config. Sends via the Graph API using the
    # client-credentials OAuth flow; the secret is Fernet-encrypted like the
    # other credential columns above. See app/services/email_service.py and
    # docs/modules/email.md for how other modules connect to the service.
    email_tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email_client_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email_client_secret_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    email_sender_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_sender_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Send mode: 'app' (client-credentials) or 'delegated' (device-code sign-in).
    email_auth_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="app", default="app"
    )
    # Delegated mode — rotating refresh token (Fernet-encrypted) + signed-in UPN.
    email_delegated_refresh_token_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    email_delegated_account: Mapped[str | None] = mapped_column(String(320), nullable=True)


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


# ── v1.49 — Quality (8D audit findings + later complaints) ──────────────


class QualityRecord(Base):
    """One 8D report row from the 8D.txt dump.

    Used by the Quality dashboard to count audit findings per level
    (1 = Major, 2 = Minor) filtered by audit type (``art`` ∈
    {BH AUD, EX AUD, IN AUD, KU AUD}). Reklamationen rows are also
    ingested so the future complaints branch can read from the same
    table without re-upload.
    """

    __tablename__ = "quality_records"
    __table_args__ = (
        Index("ix_quality_records_report_date", "report_date"),
        Index("ix_quality_records_art_level_date", "art", "level", "report_date"),
        CheckConstraint(
            "level IS NULL OR level IN (1, 2)",
            name="ck_quality_records_level",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    report_nr: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    art: Mapped[str | None] = mapped_column(String(20), nullable=True)
    level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    designation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    problem_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    # v1.51 — Spalte K (Menge) and L (akzeptierte Menge) from the 8D file.
    # Together they drive the customer-complaint rate numerator with the
    # qty_mode=total|accepted switch on the dashboard.
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 3), nullable=True)
    accepted_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 3), nullable=True
    )
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


# ── v1.50 — Delivery records (LS export from AswKpf_LS.xlsx) ───────────


class DeliveryRecord(Base):
    """One line-item on a customer delivery note (Lieferschein).

    Multiple rows share the same ``vorgang_nr`` (= Lieferschein-Nr); each
    line carries its own (pos, upos) within that delivery, so the unique
    business key is the three-column composite. Quantities feed the
    customer-complaint rate denominator (``Σ delivered / Σ complained``
    over the selected window).
    """

    __tablename__ = "delivery_records"
    __table_args__ = (
        Index("ix_delivery_records_delivery_date", "delivery_date"),
        Index("ix_delivery_records_customer_date", "customer_id", "delivery_date"),
        # v1.76 — group/join key for the Produktion Verzug KPI (order_nr →
        # Auftrag.vorgang_nr).
        Index("ix_delivery_records_order_nr", "order_nr"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="CASCADE"),
        nullable=False,
    )

    vorgang_nr: Mapped[str] = mapped_column(String(50), nullable=False)
    pos: Mapped[int] = mapped_column(Integer, nullable=False)
    upos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    typ: Mapped[str | None] = mapped_column(String(10), nullable=True)
    entry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    customer_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_city: Mapped[str | None] = mapped_column(String(255), nullable=True)

    article_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    article_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    article_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    position_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    external_order_nr: Mapped[str | None] = mapped_column(String(100), nullable=True)
    order_nr: Mapped[str | None] = mapped_column(String(100), nullable=True)

    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


# ── v1.76 — Auftragspositionen (position-level AswKpf_AUF export) ───────


class AuftragPosition(Base):
    """One line-item on a sales order (Auftrag), from the position-level
    ``AswKpf_AUF`` export.

    Structurally the AUF counterpart of :class:`DeliveryRecord`: one row per
    (order ``vorgang_nr``, ``pos``, ``upos``) carrying the confirmed
    ``lieferdatum`` (Zieltermin) for that position. Distinct from the order-book
    :class:`Auftrag` table (Sales KPIs) — this feeds the Produktion "Aufträge in
    Verzug" KPI, where per order MAX(lieferdatum) is the target against which the
    LS completion date is compared.
    """

    __tablename__ = "auftrag_positionen"
    __table_args__ = (
        UniqueConstraint(
            "vorgang_nr", "pos", "upos",
            name="uq_auftrag_positionen_vorgang_pos",
        ),
        Index("ix_auftrag_positionen_vorgang_nr", "vorgang_nr"),
        Index("ix_auftrag_positionen_lieferdatum", "lieferdatum"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="CASCADE"),
        nullable=False,
    )

    vorgang_nr: Mapped[str] = mapped_column(String(50), nullable=False)
    pos: Mapped[int] = mapped_column(Integer, nullable=False)
    upos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    typ: Mapped[str | None] = mapped_column(String(10), nullable=True)
    entry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lieferdatum: Mapped[date | None] = mapped_column(Date, nullable=True)

    customer_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_city: Mapped[str | None] = mapped_column(String(255), nullable=True)

    article_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    article_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    article_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    position_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    pos_typ_2: Mapped[str | None] = mapped_column(String(20), nullable=True)
    external_order_nr: Mapped[str | None] = mapped_column(String(100), nullable=True)

    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


# ── v1.67 — Goods-receipt records (AswKpf_WE Wareneingänge) ────────────


class GoodsReceiptRecord(Base):
    """One line-item on a supplier goods receipt (Wareneingang).

    Mirrors ``DeliveryRecord`` on the outgoing side: composite key
    ``(vorgang_nr, pos, upos)``, ``receipt_date`` is the bucket date,
    ``supplier_id`` is the join field to ``SupplierClassification``.
    Quantities feed the supplier-complaint rate denominator (filtered
    to MAT-classified suppliers via JOIN).
    """

    __tablename__ = "goods_receipt_records"
    __table_args__ = (
        Index("ix_goods_receipt_records_receipt_date", "receipt_date"),
        Index(
            "ix_goods_receipt_records_supplier_date",
            "supplier_id",
            "receipt_date",
        ),
        Index("ix_goods_receipt_records_material_group", "material_group"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="CASCADE"),
        nullable=False,
    )

    vorgang_nr: Mapped[str] = mapped_column(String(50), nullable=False)
    pos: Mapped[int] = mapped_column(Integer, nullable=False)
    upos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    typ: Mapped[str | None] = mapped_column(String(10), nullable=True)
    entry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    receipt_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    supplier_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supplier_city: Mapped[str | None] = mapped_column(String(255), nullable=True)

    article_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    article_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    article_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    position_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    order_nr: Mapped[str | None] = mapped_column(String(100), nullable=True)
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    material_group: Mapped[str | None] = mapped_column(String(50), nullable=True)
    purchase_account: Mapped[str | None] = mapped_column(String(50), nullable=True)

    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class DeliveryReliabilityRecord(Base):
    """One supplier delivery position from the Liefertreue (Einkauf) export.

    Drives the OTD / Liefertermintreue KPI: a position is *punctual* when
    ``verzug_tage <= 0``. The rate is ``count(punctual) / count(total)`` over
    the window filtered on ``delivered_date`` (actual goods-receipt date).
    Business key ``(auftrag, pos, upos)`` makes re-uploads idempotent; the
    UNIQUE constraint is created in migration v1.60.
    """

    __tablename__ = "delivery_reliability"
    __table_args__ = (
        Index("ix_delivery_reliability_delivered_date", "delivered_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="CASCADE"),
        nullable=False,
    )

    auftrag: Mapped[str] = mapped_column(String(50), nullable=False)
    pos: Mapped[int] = mapped_column(Integer, nullable=False)
    upos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    adr_nr: Mapped[str | None] = mapped_column(String(50), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Actual goods-receipt date — drives the OTD window/buckets (indexed).
    delivered_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Confirmed target date (Lieferdatum) — kept for the verification table.
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Signed delay in days; the on-time classifier (≤ 0 = punctual).
    verzug_tage: Mapped[int | None] = mapped_column(Integer, nullable=True)

    quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    article_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    article_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class TippspielTip(Base):
    """One department's score tip for one WM match (internal betting game).

    Team names are stored as the football-data feed names (mapped from the
    German Excel) so the scoring service can join a tip to its real result.
    Business key ``(home_team, away_team, department)`` makes re-uploads
    idempotent — each pairing plays once in the group stage.
    """

    __tablename__ = "tippspiel_tips"
    __table_args__ = (
        Index("ix_tippspiel_tips_match", "home_team", "away_team"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="CASCADE"),
        nullable=False,
    )

    gruppe: Mapped[str | None] = mapped_column(String(10), nullable=True)
    home_team: Mapped[str] = mapped_column(String(80), nullable=False)
    away_team: Mapped[str] = mapped_column(String(80), nullable=False)
    match_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    department: Mapped[str] = mapped_column(String(80), nullable=False)

    tip_home: Mapped[int] = mapped_column(Integer, nullable=False)
    tip_away: Mapped[int] = mapped_column(Integer, nullable=False)

    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Interessent(Base):
    """Prospect master-data row from the Adressen / Interessenten ERP export.

    One row per prospective customer. ``datum_save`` is the ERP's
    ``Datum Save`` column (when this prospect record was created /
    last persisted). The dashboard's "Interessenten" KPI counts rows
    grouped by ISO-week of ``datum_save`` — global, not per sales rep,
    because the source file has no rep column.

    ``upload_batch_id`` is nullable (ON DELETE SET NULL) so re-uploads
    can rewrite the row's batch ownership without cascading the prior
    batch's delete to historic prospect rows.
    """

    __tablename__ = "interessenten"
    __table_args__ = (
        Index("ix_interessenten_datum_save", "datum_save"),
    )

    adress_nr: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    datum_save: Mapped[date] = mapped_column(Date, nullable=False)
    upload_batch_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Offer(Base):
    """Sales-offer row from the AswKpf_ANG.txt ERP export.

    One row per Vorgang Nr.. ``erfasser`` is the ERP "Erfasst durch"
    column (the rep who created the offer); ``wert_eur`` is the EUR
    value (``Wert`` column, German decimal). The dashboard's "Angebote"
    KPI sums ``wert_eur`` per (ISO-week, erfasser).

    Deliberately separate from sales_records: AswKpf_ANG and AswKpf_AUF
    live in distinct tables so order-side KPIs (Auftragswert / chart /
    orders-distribution) can never accidentally include offer values.
    """

    __tablename__ = "offers"
    __table_args__ = (
        Index("ix_offers_datum", "datum"),
        Index("ix_offers_erfasser_datum", "erfasser", "datum"),
    )

    vorgang_nr: Mapped[str] = mapped_column(String(50), primary_key=True)
    datum: Mapped[date] = mapped_column(Date, nullable=False)
    erfasser: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wert_eur: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    adr_nr: Mapped[str | None] = mapped_column(String(50), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ort: Mapped[str | None] = mapped_column(String(255), nullable=True)
    upload_batch_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Revenue(Base):
    """Invoice / credit-note row from the AswKpf_RG.txt ERP export.

    One row per Vorgang Nr.. ``typ`` is 'RG' (Rechnung) or 'GS'
    (Gutschrift). GS rows carry a NEGATIVE ``wert_eur`` so a simple
    SUM(wert_eur) over a date window yields the net Umsatz.

    Deliberately separate from sales_records (orders, AUF) and offers
    (ANG): three distinct ERP exports, three tables. The Sales dashboard
    sources the "Umsatz" card + "Umsatzwachstum" chart from this table.
    """

    __tablename__ = "revenues"
    __table_args__ = (
        Index("ix_revenues_datum", "datum"),
        Index("ix_revenues_customer", "customer_name"),
    )

    vorgang_nr: Mapped[str] = mapped_column(String(50), primary_key=True)
    typ: Mapped[str] = mapped_column(String(8), nullable=False)
    datum: Mapped[date] = mapped_column(Date, nullable=False)
    adr_nr: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    wert_eur: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    upload_batch_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Auftrag(Base):
    """Order-book row from the AswKpf_AUF.txt ERP export (v1.54).

    Same 18-col shape as the ANG (offers) and RG (revenue) dumps —
    keyed by Vorgang Nr.. ``erfasser`` is the ERP "Erfasst durch" column,
    used as the rep token for the orders/wk/rep KPI.

    Supersedes ``sales_records`` as the source for the Sales-dashboard
    order-side KPIs (avg_order_value, total_orders, orders-distribution).
    The legacy table stays for back-compat but is no longer queried by
    the dashboard.
    """

    __tablename__ = "auftraege"
    __table_args__ = (
        Index("ix_auftraege_datum", "datum"),
        Index("ix_auftraege_erfasser_datum", "erfasser", "datum"),
        Index("ix_auftraege_customer", "customer_name"),
    )

    vorgang_nr: Mapped[str] = mapped_column(String(50), primary_key=True)
    typ: Mapped[str] = mapped_column(String(8), nullable=False)
    datum: Mapped[date] = mapped_column(Date, nullable=False)
    adr_nr: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    erfasser: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wert_eur: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    upload_batch_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


# ── v1.70 — Finanzperspektive: Materialkostenquote ──────────────────────


class MaterialMovement(Base):
    """One stock-movement line from the AswLagBew.txt export (Lagerbewegung).

    Feeds the Materialkostenquote: material *consumed* in a window is the
    net of material issues (``buchtyp='M'``, negative Bewegungsmenge) and
    their reversals (``buchtyp='SM'``, positive). Consumed qty per article
    is therefore ``-SUM(bewegungsmenge)`` over ``buchtyp IN ('M','SM')``.

    No clean business key exists in the source, so re-uploads are made
    idempotent the Kontakte way: the upload handler deletes every row whose
    ``buch_datum`` falls in the new file's date range, then bulk-inserts —
    re-uploading the same file is a no-op. ``buch_datum`` is indexed since it
    drives both the delete and the KPI window.
    """

    __tablename__ = "material_movements"
    __table_args__ = (
        Index("ix_material_movements_buch_datum", "buch_datum"),
        Index("ix_material_movements_artikelnr", "artikelnr"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="CASCADE"),
        nullable=False,
    )

    artikelnr: Mapped[str] = mapped_column(String(50), nullable=False)
    article_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    buch_datum: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Signed movement quantity; M issues are negative, SM reversals positive.
    bewegungsmenge: Mapped[Decimal | None] = mapped_column(Numeric(15, 3), nullable=True)
    buchtyp: Mapped[str | None] = mapped_column(String(10), nullable=True)
    kommentar: Mapped[str | None] = mapped_column(Text, nullable=True)

    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class InspectionRecord(Base):
    """One Qualitätsprüfung booking from the AswQs2151.txt export (v1.79).

    Each row is a single inspection line (Datum, Zeit, Benutzer, FA,
    Artikel, Bezeichnung, Buchungs-Menge, ...). ``size_class`` is derived
    at parse time from ``bezeichnung``/``produktgruppe`` — see
    :mod:`app.parsing.inspection_parser`. The source has no clean
    business key (identical booking rows are allowed), so re-uploads are
    made idempotent the Kontakte / material_movements way: delete every
    row whose ``pruef_datum`` falls in the new file's date range, then
    bulk-insert.
    """

    __tablename__ = "inspection_records"
    __table_args__ = (
        Index("ix_inspection_records_pruef_datum", "pruef_datum"),
        Index(
            "ix_inspection_records_size_class_datum",
            "size_class",
            "pruef_datum",
        ),
        CheckConstraint(
            "size_class IN ('large', 'small')",
            name="ck_inspection_records_size_class",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="CASCADE"),
        nullable=False,
    )

    pruef_datum: Mapped[date] = mapped_column(Date, nullable=False)
    pruef_zeit: Mapped[time | None] = mapped_column(Time, nullable=True)
    benutzer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fa: Mapped[str | None] = mapped_column(String(50), nullable=True)
    artikel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bezeichnung: Mapped[str | None] = mapped_column(Text, nullable=True)
    buchungs_menge: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 3), nullable=True
    )
    ausschuss_menge: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 3), nullable=True
    )
    produktgruppe: Mapped[str | None] = mapped_column(String(64), nullable=True)
    typ: Mapped[str | None] = mapped_column(String(10), nullable=True)
    size_class: Mapped[str] = mapped_column(String(10), nullable=False)
    # v1.81 — Kostenschlüssel from the AswQs2151 "RSC" column. Real
    # Qualitätsprüfung bookings carry "70000"; every other value marks
    # a stock-movement / Sonderbuchung and is skipped by the aggregation.
    rsc: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # v1.80 — per-booking KPI opt-out. When true the row still lives in
    # the table (audit trail intact) but is excluded from every KPI SUM.
    excluded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class MaterialPrice(Base):
    """One goods-receipt (Wareneingang) line from AswKpf_WE.txt, finance-scoped.

    Supplies the purchase price for the Materialkostenquote: for each
    consumed article we take the *newest* WE row (by ``datum``) and use the
    effective unit price ``pos_wert / menge`` — robust against the source's
    price-unit (the raw ``preis`` column can be per-100/1000, while
    ``pos_wert / menge`` is always the real per-unit cost).

    Owned by the Finanzperspektive (self-contained, like every other KPI
    domain); deliberately distinct from the complaint-rate
    ``goods_receipt_records`` table. Business key ``(vorgang_nr, pos, upos)``
    makes re-uploads idempotent via ``ON CONFLICT DO UPDATE``; the UNIQUE
    constraint is created in v1.70.
    """

    __tablename__ = "material_prices"
    __table_args__ = (
        Index("ix_material_prices_artnr", "artnr"),
        Index("ix_material_prices_datum", "datum"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("upload_batches.id", ondelete="CASCADE"),
        nullable=False,
    )

    vorgang_nr: Mapped[str] = mapped_column(String(50), nullable=False)
    pos: Mapped[int] = mapped_column(Integer, nullable=False)
    upos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    typ: Mapped[str | None] = mapped_column(String(10), nullable=True)
    datum: Mapped[date | None] = mapped_column(Date, nullable=True)

    artnr: Mapped[str] = mapped_column(String(50), nullable=False)
    article_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    menge: Mapped[Decimal | None] = mapped_column(Numeric(15, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preis: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    pos_wert: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
