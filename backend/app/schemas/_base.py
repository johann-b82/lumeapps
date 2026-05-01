import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, EmailStr, Field, SecretStr


class ValidationErrorDetail(BaseModel):
    row: int
    column: str
    message: str


class UploadResponse(BaseModel):
    id: int
    filename: str
    row_count: int
    error_count: int
    status: str
    errors: list[ValidationErrorDetail]


class UploadBatchSummary(BaseModel):
    id: int
    filename: str
    uploaded_at: datetime
    row_count: int
    error_count: int
    status: str

    model_config = {"from_attributes": True}


class KpiSummaryComparison(BaseModel):
    """Sibling shape for previous_period / previous_year in KpiSummary.

    Separated from KpiSummary so nested comparisons cannot themselves carry
    further nested comparisons. Null when the caller did not request the
    comparison or when the prior window had zero matching rows (DELTA-05).
    """

    total_revenue: Decimal
    avg_order_value: Decimal
    total_orders: int


class KpiSummary(BaseModel):
    total_revenue: Decimal
    avg_order_value: Decimal
    total_orders: int
    previous_period: KpiSummaryComparison | None = None
    previous_year: KpiSummaryComparison | None = None


class ChartPoint(BaseModel):
    date: str  # ISO date string "YYYY-MM-DD" (bucket-truncated by granularity)
    # `revenue` is None only in the `previous` series of ChartResponse for
    # missing trailing buckets (CHART-03 null gap). The `current` series
    # always carries concrete Decimal revenues.
    revenue: Decimal | None = None


class ChartResponse(BaseModel):
    """Wrapped chart response (Phase 8 breaking change vs. bare list[ChartPoint]).

    `current` is always a concrete bucket list (possibly empty).
    `previous` is null unless the caller requested a comparison via
    ``comparison=previous_period|previous_year`` with ``prev_start`` +
    ``prev_end`` present. Buckets in `previous` are positionally aligned to
    `current` — their ``date`` strings are rewritten to the current X-axis
    dates so Recharts can share a single date domain across both series.
    Missing trailing prior buckets are emitted as ``revenue=None`` (CHART-03).
    """

    current: list[ChartPoint]
    previous: list[ChartPoint] | None = None


class LatestUploadResponse(BaseModel):
    uploaded_at: datetime | None  # None when no uploads exist


# --------------------------------------------------------------------------
# Phase 4 — Settings schemas (BRAND-09 strict color validation)
# --------------------------------------------------------------------------
# Per D-10: matches oklch(L C H) where
#   L is 0..1 decimal OR 0..100 percent
#   C is numeric (0..0.5-ish in practice)
#   H is numeric with optional 'deg' suffix
# Alpha (oklch(L C H / alpha)) is rejected — frontend culori emits plain form.
_OKLCH_RE = re.compile(
    r"^oklch\(\s*"
    r"(?:0|1|0?\.\d+|100%|\d{1,2}(?:\.\d+)?%?)"      # L
    r"\s+"
    r"(?:\d+(?:\.\d+)?)"                              # C
    r"\s+"
    r"(?:-?\d+(?:\.\d+)?)(?:deg)?"                    # H
    r"\s*\)$"
)
# Per D-10: full CSS-injection blacklist.
_FORBIDDEN_CHARS: frozenset[str] = frozenset(";{}\"'`\\<>")
_FORBIDDEN_TOKENS: tuple[str, ...] = ("url(", "expression(", "/*", "*/")


def _validate_oklch(value: str) -> str:
    """Strict oklch validator. Belt-and-braces: blacklist runs BEFORE regex."""
    if not isinstance(value, str):
        raise ValueError("color must be a string")
    if any(ch in _FORBIDDEN_CHARS for ch in value):
        raise ValueError("color contains forbidden character")
    lowered = value.lower()
    if any(tok in lowered for tok in _FORBIDDEN_TOKENS):
        raise ValueError("color contains forbidden token")
    if not _OKLCH_RE.match(value):
        raise ValueError("color must be a valid oklch(L C H) string")
    return value


OklchColor = Annotated[str, AfterValidator(_validate_oklch)]


class SettingsUpdate(BaseModel):
    """Request body for PUT /api/settings. Does NOT include logo bytes (D-05)."""

    color_primary: OklchColor
    color_accent: OklchColor
    color_background: OklchColor
    color_foreground: OklchColor
    color_muted: OklchColor
    color_destructive: OklchColor
    app_name: Annotated[str, Field(min_length=1, max_length=100)]
    # Personio credentials — Optional; None means "don't change existing value" (D-03)
    personio_client_id: str | None = None
    personio_client_secret: str | None = None
    # Personio KPI configuration — arrays (Phase 19, D-03)
    personio_sync_interval_h: Literal[0, 1, 6, 24, 168] | None = None
    personio_sick_leave_type_id: list[int] | None = None
    personio_production_dept: list[str] | None = None
    personio_skill_attr_key: list[str] | None = None
    # HR KPI targets — None means "don't change"
    target_overtime_ratio: float | None = None
    target_sick_leave_ratio: float | None = None
    target_fluctuation: float | None = None
    target_revenue_per_employee: float | None = None
    # v1.15 Sensor Monitor — admin writes (Phase 40-01)
    # None means "don't change" (same pattern as Personio / HR targets above).
    # Known limitation (40-01): there is no sentinel for "clear threshold back
    # to NULL" — admin must use a future reset flow. A blank input in the UI
    # maps to "don't change". Carry-forward for 40-02 or a dedicated reset path.
    sensor_poll_interval_s: int | None = Field(default=None, ge=5, le=86400)
    sensor_temperature_min: Decimal | None = None
    sensor_temperature_max: Decimal | None = None
    sensor_humidity_min: Decimal | None = None
    sensor_humidity_max: Decimal | None = None


class SettingsRead(BaseModel):
    """Response body for GET/PUT /api/settings. Includes logo_url (D-03)."""

    color_primary: str
    color_accent: str
    color_background: str
    color_foreground: str
    color_muted: str
    color_destructive: str
    app_name: str
    logo_url: str | None
    logo_updated_at: datetime | None
    # Personio write-only — only expose boolean, never raw credentials (D-03, PERS-01)
    personio_has_credentials: bool = False
    # Personio KPI configuration — arrays (Phase 19)
    personio_sync_interval_h: int = 1
    personio_sick_leave_type_id: list[int] = []
    personio_production_dept: list[str] = []
    personio_skill_attr_key: list[str] = []
    # HR KPI targets
    target_overtime_ratio: float | None = None
    target_sick_leave_ratio: float | None = None
    target_fluctuation: float | None = None
    target_revenue_per_employee: float | None = None
    # Phase 39-02 — Sensor config surfaced read-only (admin writes arrive Phase 40).
    # Decimal serializes as string; frontend parses via Number().
    sensor_poll_interval_s: int = 60
    sensor_temperature_min: Decimal | None = None
    sensor_temperature_max: Decimal | None = None
    sensor_humidity_min: Decimal | None = None
    sensor_humidity_max: Decimal | None = None

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------
# Phase 13 Plan 01 — Sync and Personio schemas
# --------------------------------------------------------------------------


class SyncResult(BaseModel):
    employees_synced: int
    attendance_synced: int
    absences_synced: int
    status: Literal["ok", "error"]
    error_message: str | None = None


class SyncTestResult(BaseModel):
    success: bool
    error: str | None = None


class AbsenceTypeOption(BaseModel):
    id: int
    name: str


class PersonioOptions(BaseModel):
    absence_types: list[AbsenceTypeOption]
    departments: list[str]
    skill_attributes: list[str] = []
    error: str | None = None


# --------------------------------------------------------------------------
# Phase 14 Plan 01 — Sync meta schema
# --------------------------------------------------------------------------


class SyncMetaRead(BaseModel):
    last_synced_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------
# Phase 15 Plan 01 — HR KPI schemas
# --------------------------------------------------------------------------


class HrKpiValue(BaseModel):
    """A single HR KPI for one calendar month window.

    value=None + is_configured=True  -> no data yet (em-dash)
    value=None + is_configured=False -> setting not configured ("nicht konfiguriert")
    Per D-06/D-07/D-08.
    """

    value: float | None = None
    is_configured: bool = True
    previous_period: float | None = None
    previous_year: float | None = None


class HrKpiResponse(BaseModel):
    overtime_ratio: HrKpiValue
    sick_leave_ratio: HrKpiValue
    fluctuation: HrKpiValue
    skill_development: HrKpiValue
    revenue_per_production_employee: HrKpiValue


# --------------------------------------------------------------------------
# Data table schemas — raw record listing
# --------------------------------------------------------------------------

class SalesRecordRead(BaseModel):
    id: int
    order_number: str
    customer_name: str | None = None
    city: str | None = None
    order_date: date | None = None
    total_value: float | None = None
    remaining_value: float | None = None
    responsible_person: str | None = None
    project_name: str | None = None
    status_code: int | None = None

    model_config = {"from_attributes": True}


class HrKpiHistoryPoint(BaseModel):
    month: str  # "2026-01"
    overtime_ratio: float | None = None
    sick_leave_ratio: float | None = None
    fluctuation: float | None = None
    revenue_per_production_employee: float | None = None


class EmployeeRead(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    status: str | None = None
    department: str | None = None
    position: str | None = None
    hire_date: date | None = None
    termination_date: date | None = None
    weekly_working_hours: float | None = None
    total_hours: float = 0.0
    overtime_hours: float = 0.0
    overtime_ratio: float | None = None

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------
# Phase 27 — Auth schemas
# --------------------------------------------------------------------------
from app.security.roles import Role  # noqa: E402


class CurrentUser(BaseModel):
    id: UUID
    email: EmailStr
    role: Role


# --------------------------------------------------------------------------
# v1.15 Sensor schemas (Phase 38)
# --------------------------------------------------------------------------
# SecretStr imported at top; Decimal + datetime already imported at top.


_HEX_COLOR_RE = r"^#[0-9a-fA-F]{6}$"


class SensorRead(BaseModel):
    """Admin-facing sensor config read. community is NEVER included (PITFALLS C-3)."""
    id: int
    name: str
    host: str
    port: int
    # community is intentionally OMITTED — never echo the ciphertext, never decrypt it
    # into a response. Admin UI treats community as write-only.
    temperature_oid: str | None
    humidity_oid: str | None
    temperature_scale: Decimal
    humidity_scale: Decimal
    enabled: bool
    chart_color: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SensorCreate(BaseModel):
    """Admin creates a sensor. community accepts empty string for devices that
    don't require SNMP community auth (v1.27 — relaxed from min_length=1)."""
    name: str = Field(..., min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=161, ge=1, le=65535)
    community: SecretStr = Field(default=SecretStr(""))
    temperature_oid: str | None = Field(default=None, max_length=255)
    humidity_oid: str | None = Field(default=None, max_length=255)
    temperature_scale: Decimal = Field(default=Decimal("1.0"), gt=Decimal("0"))
    humidity_scale: Decimal = Field(default=Decimal("1.0"), gt=Decimal("0"))
    enabled: bool = True
    # v1.39: optional `#rrggbb` chart color. NULL → frontend palette fallback.
    chart_color: str | None = Field(default=None, pattern=_HEX_COLOR_RE)


class SensorUpdate(BaseModel):
    """Partial sensor edit. All fields optional; community accepts empty string."""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    community: SecretStr | None = Field(default=None)
    temperature_oid: str | None = Field(default=None, max_length=255)
    humidity_oid: str | None = Field(default=None, max_length=255)
    temperature_scale: Decimal | None = Field(default=None, gt=Decimal("0"))
    humidity_scale: Decimal | None = Field(default=None, gt=Decimal("0"))
    enabled: bool | None = None
    chart_color: str | None = Field(default=None, pattern=_HEX_COLOR_RE)


class SensorReadingRead(BaseModel):
    """One sensor_readings row."""
    id: int
    sensor_id: int
    recorded_at: datetime
    temperature: Decimal | None
    humidity: Decimal | None
    error_code: str | None

    model_config = {"from_attributes": True}


class PollNowResult(BaseModel):
    """Response shape for POST /api/sensors/poll-now."""
    sensors_polled: int
    errors: list[str]


class SnmpProbeRequest(BaseModel):
    """Probe an uncommitted sensor draft config for live temp+humidity."""
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=161, ge=1, le=65535)
    community: SecretStr = Field(default=SecretStr(""))
    temperature_oid: str | None = Field(default=None, max_length=255)
    humidity_oid: str | None = Field(default=None, max_length=255)
    temperature_scale: Decimal = Field(default=Decimal("1.0"), gt=Decimal("0"))
    humidity_scale: Decimal = Field(default=Decimal("1.0"), gt=Decimal("0"))


class SnmpWalkRequest(BaseModel):
    """Walk an OID tree for the OID-Finder admin UI."""
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=161, ge=1, le=65535)
    community: SecretStr = Field(default=SecretStr(""))
    base_oid: str = Field(..., min_length=1, max_length=255)
    max_results: int = Field(default=200, ge=1, le=500)


# ── v1.41 — sales contacts ──────────────────────────────────────────────
# v1.42: removed SalesAlias schemas + UnmappedTokenSample. Reps are
# identified directly by the Wer token from the Kontakte file; no
# Personio binding remains.


class ContactsUploadResponse(BaseModel):
    rows_inserted: int
    rows_replaced: int
    date_range_from: date | None
    date_range_to: date | None


class ContactsWeeklyEmployeeBucket(BaseModel):
    erstkontakte: int
    interessenten: int
    visits: int
    angebote: int


class ContactsWeeklyWeek(BaseModel):
    iso_year: int
    iso_week: int
    label: str
    # Keyed by the Wer token (e.g. "GUENDEL"). v1.41 used personio_employee_id
    # int keys; v1.42 dropped the binding.
    per_employee: dict[str, ContactsWeeklyEmployeeBucket]


class ContactsWeeklyResponse(BaseModel):
    weeks: list[ContactsWeeklyWeek]


class OrdersDistributionResponse(BaseModel):
    orders_per_week_per_rep: float
    top3_share_pct: float
    remaining_share_pct: float
    top3_customers: list[str]


__all__ = [
    "ValidationErrorDetail",
    "UploadResponse",
    "UploadBatchSummary",
    "KpiSummaryComparison",
    "KpiSummary",
    "ChartPoint",
    "ChartResponse",
    "LatestUploadResponse",
    "OklchColor",
    "SettingsUpdate",
    "SettingsRead",
    "SyncResult",
    "SyncTestResult",
    "AbsenceTypeOption",
    "PersonioOptions",
    "SyncMetaRead",
    "HrKpiValue",
    "HrKpiResponse",
    "SalesRecordRead",
    "HrKpiHistoryPoint",
    "EmployeeRead",
    "CurrentUser",
    "SensorRead",
    "SensorCreate",
    "SensorUpdate",
    "SensorReadingRead",
    "PollNowResult",
    "SnmpProbeRequest",
    "SnmpWalkRequest",
    # v1.41 sales contacts
    "ContactsUploadResponse",
    "ContactsWeeklyEmployeeBucket",
    "ContactsWeeklyWeek",
    "ContactsWeeklyResponse",
    "OrdersDistributionResponse",
]
