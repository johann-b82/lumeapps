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
    # v1.55 — Sales-dashboard targets (None means "don't change"). Use a
    # sentinel "clear" path later if explicit unset is needed; current
    # frontend treats missing key as "don't change" and falls back to a
    # baked-in default when the DB value is NULL.
    target_sales_erstkontakte: float | None = None
    target_sales_interessenten: float | None = None
    target_sales_besuche: float | None = None
    target_sales_angebote_eur: float | None = None
    target_sales_orders_per_rep_eur: float | None = None
    # v1.60 — Quality KPI targets (None = "don't change"). Complaint rates
    # are fractions (0.02 = 2 %); finding counts are integer thresholds.
    target_complaint_rate_customer: float | None = None
    target_complaint_rate_internal: float | None = None
    target_complaint_rate_supplier: float | None = None
    target_complaint_rate_subcontractor: float | None = None
    target_audit_findings_level1: int | None = None
    target_audit_findings_level2: int | None = None
    target_inspection_large: int | None = None
    target_inspection_small: int | None = None
    # v1.71 / v1.72 — Finance KPI targets (cost ratios as fractions)
    target_material_cost_ratio: float | None = None
    target_personnel_cost_ratio: float | None = None
    # v1.77 — Produktion Verzug target (max Verzugsquote as fraction)
    target_produktion_verzug: float | None = None
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
    # v1.57 World Cup signage — None means "don't change" (credential pattern).
    worldcup_api_key: str | None = None
    worldcup_refresh_seconds: int | None = Field(default=None, ge=30, le=3600)
    # v1.65 ATR fileserver — None means "don't change"; password is write-only
    atr_smb_host: str | None = None
    atr_smb_share: str | None = None
    atr_smb_domain: str | None = None
    atr_smb_user: str | None = None
    atr_smb_password: str | None = None
    atr_input_path: str | None = None
    atr_output_path: str | None = None
    atr_archive_path: str | None = None
    atr_scan_interval_s: int | None = None
    atr_auto_mode: bool | None = None


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
    # v1.55 — Sales-dashboard targets
    target_sales_erstkontakte: float | None = None
    target_sales_interessenten: float | None = None
    target_sales_besuche: float | None = None
    target_sales_angebote_eur: float | None = None
    target_sales_orders_per_rep_eur: float | None = None
    # v1.60 — Quality KPI targets
    target_complaint_rate_customer: float | None = None
    target_complaint_rate_internal: float | None = None
    target_complaint_rate_supplier: float | None = None
    target_complaint_rate_subcontractor: float | None = None
    target_audit_findings_level1: int | None = None
    target_audit_findings_level2: int | None = None
    target_inspection_large: int | None = None
    target_inspection_small: int | None = None
    # v1.71 / v1.72 — Finance KPI targets (cost ratios as fractions)
    target_material_cost_ratio: float | None = None
    target_personnel_cost_ratio: float | None = None
    # v1.77 — Produktion Verzug target (max Verzugsquote as fraction)
    target_produktion_verzug: float | None = None
    # Phase 39-02 — Sensor config surfaced read-only (admin writes arrive Phase 40).
    # Decimal serializes as string; frontend parses via Number().
    sensor_poll_interval_s: int = 60
    sensor_temperature_min: Decimal | None = None
    sensor_temperature_max: Decimal | None = None
    sensor_humidity_min: Decimal | None = None
    sensor_humidity_max: Decimal | None = None
    # v1.57 World Cup signage — key is write-only, expose only the boolean.
    worldcup_has_api_key: bool = False
    worldcup_refresh_seconds: int = 60
    # v1.65 ATR fileserver — password is write-only; expose only the boolean
    atr_smb_host: str | None = None
    atr_smb_share: str | None = None
    atr_smb_domain: str | None = None
    atr_smb_user: str | None = None
    atr_smb_has_password: bool = False
    atr_input_path: str | None = None
    atr_output_path: str | None = None
    atr_archive_path: str | None = None
    atr_scan_interval_s: int = 0
    atr_auto_mode: bool = False

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
    """One sensor_readings row OR a synthesised time-bucket average.

    ``id`` is null when the row is a bucket average returned by the
    long-window downsample path (``hours > 24`` on
    ``/api/sensors/{id}/readings``). Raw rows always carry a real id.
    """
    id: int | None = None
    sensor_id: int
    recorded_at: datetime
    temperature: Decimal | None
    humidity: Decimal | None
    error_code: str | None = None

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
    # v1.51: interessenten removed from the per-employee bucket — the new
    # Adressen/Interessenten data source has no rep column, so the field
    # moves to ``ContactsWeeklyWeek.interessenten`` as a global per-week
    # total. Kept at zero for backwards-compatible payloads from older
    # clients that still read it via dict access.
    visits: int
    # v1.52: onl (online meetings) is a separate KPI from visits (ORT).
    # Both come from sales_contacts but distinguish in-person vs online.
    onl: int = 0
    # v1.52: angebote is now an EUR value (sum of Wert from the offers
    # table), not a count. Float so JSON cleanly carries non-int decimals
    # like 322611.16.
    angebote: float
    # v1.56-b: weekly €-volume per rep from the auftraege table, plotted
    # as the 5th bar chart in the Vertriebsaktivität card.
    orders_eur: float = 0


class ContactsWeeklyWeek(BaseModel):
    iso_year: int
    iso_week: int
    label: str
    # v1.51: global Interessenten count for the week, sourced from the
    # interessenten table (Adress-Nr + Datum Save). Not aggregated per
    # employee — the source file carries no rep token.
    interessenten: int = 0
    # Keyed by the Wer token (e.g. "GUENDEL"). v1.41 used personio_employee_id
    # int keys; v1.42 dropped the binding.
    per_employee: dict[str, ContactsWeeklyEmployeeBucket]


class ContactsWeeklyResponse(BaseModel):
    weeks: list[ContactsWeeklyWeek]


class TopCustomer(BaseModel):
    name: str
    total_value: float


class OrdersDistributionResponse(BaseModel):
    orders_per_week_per_rep: float
    top3_share_pct: float
    remaining_share_pct: float
    top3_customers: list[TopCustomer]


# v1.56-c — Customer-share waterfall for the two-source Kundenanteil cards.


class CustomerShareEntry(BaseModel):
    name: str
    total_value: float
    share_pct: float


class CustomerShareResponse(BaseModel):
    """Top-N customer share for either the Aufträge or Umsatz card.

    ``source`` is round-tripped from the query param so the frontend can
    label the card without re-deriving from the URL. ``top_share_pct`` is
    the cumulative share of the first ``top_n`` rows; the long-tail rest
    is ``remaining_share_pct = 100 − top_share_pct``.
    """

    source: str
    top_n: int
    total_value: float
    top_share_pct: float
    remaining_share_pct: float
    top_customers: list[CustomerShareEntry]


# --------------------------------------------------------------------------
# v1.49 — Quality (8D audit findings)
# --------------------------------------------------------------------------


class QualityUploadResponse(BaseModel):
    rows_inserted: int
    rows_updated: int = 0
    errors: list[ValidationErrorDetail]


class DeliveryUploadResponse(BaseModel):
    rows_inserted: int
    rows_updated: int = 0
    errors: list[ValidationErrorDetail]


class AuftragPositionenUploadResponse(BaseModel):
    """Response from POST /api/upload-auftrag-positionen (position-level AUF)."""

    rows_inserted: int
    rows_updated: int = 0
    errors: list[ValidationErrorDetail]


class GoodsReceiptUploadResponse(BaseModel):
    rows_inserted: int
    rows_updated: int = 0
    errors: list[ValidationErrorDetail]


class InteressentenUploadResponse(BaseModel):
    """Response from POST /api/upload-interessenten.

    Mirrors QualityUploadResponse: an upsert on Adress-Nr., with a
    breakdown of how many rows were genuine inserts vs. updates of an
    existing prospect record.
    """

    rows_inserted: int
    rows_updated: int = 0
    errors: list[ValidationErrorDetail]


class AngeboteUploadResponse(BaseModel):
    """Response from POST /api/upload-angebote.

    Mirrors the InteressentenUploadResponse upsert shape — the offers
    file is keyed by Vorgang Nr., so re-uploads update rather than
    inserting duplicates.
    """

    rows_inserted: int
    rows_updated: int = 0
    errors: list[ValidationErrorDetail]


class RevenueUploadResponse(BaseModel):
    """Response from POST /api/upload-umsatz.

    Same upsert shape — the AswKpf_RG dump is keyed by Vorgang Nr., so
    re-uploads update rather than inserting duplicates.
    """

    rows_inserted: int
    rows_updated: int = 0
    errors: list[ValidationErrorDetail]


class AuftraegeUploadResponse(BaseModel):
    """Response from POST /api/upload-auftraege.

    The AswKpf_AUF dump is keyed by Vorgang Nr.; same upsert shape as the
    ANG and RG dumps.
    """

    rows_inserted: int
    rows_updated: int = 0
    errors: list[ValidationErrorDetail]


class AuditFindingsValue(BaseModel):
    """Counts for one window with optional prior baselines."""

    level_1: int
    level_2: int
    previous_period_level_1: int | None = None
    previous_period_level_2: int | None = None
    previous_year_level_1: int | None = None
    previous_year_level_2: int | None = None


class AuditFindingRow(BaseModel):
    """One row of the findings list shown under the Quality charts.

    Mirrors a subset of QualityRecord columns — only what the verification
    table needs (no big text blobs like problem_description; the table is a
    fast scan-and-spot tool, not a drill-down detail view).
    """

    report_nr: str
    report_date: date | None = None
    art: str | None = None
    level: int | None = None
    issuer: str | None = None
    customer_name: str | None = None
    customer_id: str | None = None
    designation: str | None = None
    status_code: str | None = None

    model_config = {"from_attributes": True}


class ComplaintRateValue(BaseModel):
    """Customer-complaint rate KPI for a window.

    ``rate`` is a fraction (0.0327 → 3.27 %). NULL if the window had no
    deliveries (division-by-zero guard).
    """

    rate: float | None = None
    complaint_qty: float
    delivered_qty: float
    previous_period: float | None = None
    previous_year: float | None = None


class InspectionsValue(BaseModel):
    """Inspection counts for one window — large + small products.

    Stub schema (v1.70) — the aggregation returns 0 for both counts
    until the input pipeline (upload file + derivation from existing
    data) is specified. Delta baselines mirror the audit-findings shape.
    """

    large_count: int = 0
    small_count: int = 0
    previous_period_large: int | None = None
    previous_period_small: int | None = None
    previous_year_large: int | None = None
    previous_year_small: int | None = None


class InspectionsHistoryPoint(BaseModel):
    month: str
    large_count: int = 0
    small_count: int = 0


class InspectionBookingRow(BaseModel):
    """One raw AswQs2151 booking row for the verification table (v1.80).

    Distinct from :class:`InspectionListRow` (which is aggregated per
    product name): this schema is one-to-one with ``inspection_records``
    so the user can tick individual bookings out of the KPI when they
    spot a fat-finger entry.
    """

    id: int
    pruef_datum: str | None = None
    pruef_zeit: str | None = None
    benutzer: str | None = None
    fa: str | None = None
    artikel: str | None = None
    bezeichnung: str | None = None
    size_class: str
    produktgruppe: str | None = None
    buchungs_menge: float = 0.0
    ausschuss_menge: float = 0.0
    excluded: bool = False


class InspectionExcludeUpdate(BaseModel):
    """Body of PATCH /api/quality/inspections/bookings/{id}."""

    excluded: bool


class InspectionListRow(BaseModel):
    """One aggregated row per product name in the verification table.

    Backs GET /api/quality/inspections/list — rows grouped by
    ``(bezeichnung, size_class)`` in the window. ``scrap_rate`` is a
    fraction (0.02 → 2 %) or NULL when nothing was booked, so the
    frontend can format it consistently with other rate columns.
    """

    bezeichnung: str | None = None
    size_class: str  # 'large' or 'small'
    produktgruppe: str | None = None
    bookings: int = 0
    total_qty: float = 0.0
    scrap_qty: float = 0.0
    scrap_rate: float | None = None
    inspectors: int = 0
    first_date: str | None = None
    last_date: str | None = None


class ComplaintRateHistoryPoint(BaseModel):
    month: str
    rate: float | None = None
    complaint_qty: float
    delivered_qty: float


class DeliveryReliabilityUploadResponse(BaseModel):
    """Response from POST /api/upload-delivery-reliability.

    Upsert on (auftrag, pos, upos). ``period_from`` / ``period_to`` echo the
    Auswertung range parsed from the file's title row (ISO dates, or null
    when the export carried no title line).
    """

    rows_inserted: int
    rows_updated: int = 0
    period_from: str | None = None
    period_to: str | None = None
    errors: list[ValidationErrorDetail]


class OtdValue(BaseModel):
    """Liefertermintreue / OTD KPI for a window.

    ``rate`` is a fraction (0.92 → 92 %) = punctual / total. NULL when the
    window had no delivery positions. Higher is better.
    """

    rate: float | None = None
    punctual_count: int
    total_count: int
    avg_delay: float | None = None
    previous_period: float | None = None
    previous_year: float | None = None


class ProductionVerzugValue(BaseModel):
    """Produktion — "Aufträge in Verzug (Seriengeschäft)" KPI for a window.

    Counted by *order* (Auftrag), not by delivery position: an order is in
    Verzug when its latest LS-Lieferdatum falls after the order's confirmed
    Lieferdatum (Zieltermin). ``rate`` = in_verzug / total, a fraction
    (0.12 → 12 %). NULL when the window had no matching orders. Lower is
    better — the frontend renders deltas in Termintreue-complement space.
    """

    rate: float | None = None
    in_verzug_count: int
    total_count: int
    avg_delay: float | None = None
    previous_period: float | None = None
    previous_year: float | None = None


class ProductionVerzugHistoryPoint(BaseModel):
    month: str
    rate: float | None = None
    in_verzug_count: int
    total_count: int


class ProductionVerzugRow(BaseModel):
    """One delivered-late order for the "Aufträge in Verzug" table."""

    vorgang_nr: str
    customer_name: str | None = None
    adr_nr: str | None = None
    target_date: date | None = None
    actual_date: date | None = None
    verzug_tage: int | None = None

    model_config = {"from_attributes": True}


class ProductionOverdueRow(BaseModel):
    """One open & overdue order (no Lieferschein, Zieltermin already past)."""

    vorgang_nr: str
    customer_name: str | None = None
    adr_nr: str | None = None
    target_date: date | None = None
    days_overdue: int | None = None

    model_config = {"from_attributes": True}


class OtdHistoryPoint(BaseModel):
    month: str
    rate: float | None = None
    punctual_count: int
    total_count: int


class OtdRow(BaseModel):
    """One row of the OTD verification table."""

    auftrag: str
    pos: int
    upos: int
    adr_nr: str | None = None
    supplier_name: str | None = None
    delivered_date: date | None = None
    target_date: date | None = None
    verzug_tage: int | None = None
    quantity: float | None = None
    unit: str | None = None
    article_number: str | None = None
    article_name: str | None = None

    model_config = {"from_attributes": True}


# ── v1.70 — Finanzperspektive: Materialkostenquote ──────────────────────


class MaterialMovementsUploadResponse(BaseModel):
    """Response from POST /api/upload-material-movements.

    Replace-by-date-range insert (no business key in the source). Every
    existing row whose ``buch_datum`` falls inside the file's date range is
    deleted first, so re-uploading the same file is a no-op. ``date_range_*``
    echo the min/max BuchDatum of the uploaded rows.
    """

    rows_inserted: int
    rows_replaced: int = 0
    date_range_from: date | None = None
    date_range_to: date | None = None
    errors: list[ValidationErrorDetail]


class MaterialPricesUploadResponse(BaseModel):
    """Response from POST /api/upload-material-prices.

    Upsert on (vorgang_nr, pos, upos); ``ON CONFLICT DO UPDATE`` overwrites
    every data column on re-upload.
    """

    rows_inserted: int
    rows_updated: int = 0
    errors: list[ValidationErrorDetail]


class InspectionsUploadResponse(BaseModel):
    """Response from POST /api/upload-inspections (v1.79).

    Replace-by-date-range insert (no clean business key in the source —
    identical booking rows are legitimate). Every existing
    ``inspection_records`` row whose ``pruef_datum`` falls inside the
    file's date range is deleted first, so re-uploading the same file
    is a no-op. ``date_range_*`` echo the min/max Datum of the uploaded
    rows.
    """

    rows_inserted: int
    rows_replaced: int = 0
    small_count: int = 0
    large_count: int = 0
    date_range_from: date | None = None
    date_range_to: date | None = None
    errors: list[ValidationErrorDetail]


class MaterialCostRatioValue(BaseModel):
    """Materialkostenquote KPI for a window.

    ``ratio`` is a fraction (0.34 → 34 %) = material_cost / revenue. NULL when
    the window had no revenue. Lower is better. ``unmatched_articles`` counts
    consumed articles that had no WE purchase price (excluded from the cost).
    """

    ratio: float | None = None
    material_cost: float
    revenue: float
    matched_articles: int
    unmatched_articles: int
    previous_period: float | None = None
    previous_year: float | None = None


class MaterialCostRatioHistoryPoint(BaseModel):
    month: str
    ratio: float | None = None
    material_cost: float
    revenue: float


class MaterialCostRatioRow(BaseModel):
    """One row of the Materialkostenquote verification table (per article)."""

    artikelnr: str
    article_name: str | None = None
    consumed_qty: float
    unit_price: float | None = None
    material_cost: float | None = None
    has_price: bool


class PersonnelCostRatioValue(BaseModel):
    """Personalkostenquote KPI for a window.

    ``ratio`` is a fraction (0.30 → 30 %) = personnel_cost / revenue. NULL when
    the window had no revenue. Lower is better. ``personnel_cost`` is gross
    salary (no employer overhead); ``headcount`` is the number of employees
    that contributed cost in the window.
    """

    ratio: float | None = None
    personnel_cost: float
    revenue: float
    headcount: int
    previous_period: float | None = None
    previous_year: float | None = None


class PersonnelCostRatioHistoryPoint(BaseModel):
    month: str
    ratio: float | None = None
    personnel_cost: float
    revenue: float


class PersonnelCostRatioRow(BaseModel):
    """One row of the Personalkostenquote verification table (per department).

    Aggregated per department — individual salaries are never exposed.
    """

    department: str
    headcount: int
    personnel_cost: float


class TippspielUploadResponse(BaseModel):
    """Response from POST /api/upload-tippspiel."""

    rows_inserted: int
    rows_updated: int = 0
    departments: list[str]
    errors: list[ValidationErrorDetail]


class TippspielRankRow(BaseModel):
    """One department row of the Tippspiel ranking."""

    rank: int
    department: str
    last_points: int
    total_points: int


class TippspielFeed(BaseModel):
    """Tippspiel ranking feed for the signage embed."""

    refresh_seconds: int
    error: str | None = None
    ranking: list[TippspielRankRow] = []


class CustomerComplaintRow(BaseModel):
    """One row of the customer-complaint verification table."""

    report_nr: str
    report_date: date | None = None
    art: str | None = None
    issuer: str | None = None
    customer_name: str | None = None
    customer_id: str | None = None
    designation: str | None = None
    status_code: str | None = None
    quantity: float | None = None
    accepted_quantity: float | None = None

    model_config = {"from_attributes": True}


class AuditFindingsHistoryPoint(BaseModel):
    """Per-bucket finding counts for the history chart.

    Beyond the ``level_1`` / ``level_2`` totals each point carries one
    ``level_<n>_<ART_CODE>`` field per (level, art) combination from the
    active filter (e.g. ``level_1_BH_AUD``). These are the Recharts
    ``dataKey`` values the frontend stacks into the two-panel chart.
    Pydantic config is extra="allow" so the variable-key art breakdown
    passes through without an explicit field per code.
    """

    model_config = {"extra": "allow"}

    month: str  # same label format as HrKpiHistoryPoint
    level_1: int
    level_2: int


__all__ = [
    "ValidationErrorDetail",
    "UploadResponse",
    "UploadBatchSummary",
    "QualityUploadResponse",
    "DeliveryUploadResponse",
    "AuftragPositionenUploadResponse",
    "GoodsReceiptUploadResponse",
    "InteressentenUploadResponse",
    "AngeboteUploadResponse",
    "RevenueUploadResponse",
    "AuftraegeUploadResponse",
    "AuditFindingsValue",
    "AuditFindingRow",
    "AuditFindingsHistoryPoint",
    "ComplaintRateValue",
    "ComplaintRateHistoryPoint",
    "CustomerComplaintRow",
    "InspectionsValue",
    "InspectionsHistoryPoint",
    "InspectionListRow",
    "InspectionBookingRow",
    "InspectionExcludeUpdate",
    "DeliveryReliabilityUploadResponse",
    "OtdValue",
    "ProductionVerzugValue",
    "ProductionVerzugHistoryPoint",
    "ProductionVerzugRow",
    "ProductionOverdueRow",
    "OtdHistoryPoint",
    "OtdRow",
    # v1.70 Finanzperspektive — Materialkostenquote
    "MaterialMovementsUploadResponse",
    "MaterialPricesUploadResponse",
    "InspectionsUploadResponse",
    "MaterialCostRatioValue",
    "MaterialCostRatioHistoryPoint",
    "MaterialCostRatioRow",
    "PersonnelCostRatioValue",
    "PersonnelCostRatioHistoryPoint",
    "PersonnelCostRatioRow",
    "TippspielUploadResponse",
    "TippspielRankRow",
    "TippspielFeed",
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
    "TopCustomer",
    "OrdersDistributionResponse",
    "CustomerShareEntry",
    "CustomerShareResponse",
]
