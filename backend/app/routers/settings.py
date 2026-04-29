"""Settings API — SET-02, SET-03, SET-04, BRAND-01, BRAND-02, BRAND-04, BRAND-09.

Endpoints:
  GET  /api/settings        -> SettingsRead
  PUT  /api/settings        -> SettingsRead (422 on invalid colors per BRAND-09)
  POST /api/settings/logo   -> SettingsRead (422 on bad/oversize/malicious upload)
  GET  /api/settings/logo   -> raw bytes with ETag + Cache-Control (304 on If-None-Match)

Mixed gate (Phase B convention):
    Viewer-readable: GET /api/settings, GET /api/settings/personio-options,
                     GET /api/settings/logo
    Public:          GET /api/settings/logo/public (no auth — public_router)
    Admin-only:      PUT /api/settings, POST /api/settings/logo
    Per-route ``Depends(require_admin)`` is used here because viewer reads
    and admin writes coexist on the same prefix (CLAUDE.md Conventions §
    "Auth dependencies live at the router level except mixed-gate routers").
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.security.directus_auth import get_current_user, require_admin
from app.defaults import DEFAULT_SETTINGS
from app.models import AppSettings
from app.schemas import AbsenceTypeOption, PersonioOptions, SettingsRead, SettingsUpdate
from app.security.fernet import decrypt_credential, encrypt_credential
from app.security.logo_validation import SvgRejected, sanitize_svg, sniff_mime
from app.services.personio_client import PersonioAPIError, PersonioClient

router = APIRouter(
    prefix="/api/settings",
    dependencies=[Depends(get_current_user)],
)

public_router = APIRouter(prefix="/api/settings", tags=["settings"])

ALLOWED_LOGO_EXTENSIONS = {".png", ".svg"}
MAX_LOGO_BYTES = 1 * 1024 * 1024  # 1 MB — D-16


# --- Helpers -------------------------------------------------------------

async def _get_singleton(db: AsyncSession) -> AppSettings:
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        # D-20: migrate service should have seeded this — defensive fallback.
        raise HTTPException(
            status_code=500,
            detail="app_settings singleton missing — run migrations",
        )
    return row


def _build_read(row: AppSettings) -> SettingsRead:
    logo_url: str | None = None
    if row.logo_data is not None and row.logo_updated_at is not None:
        ts = int(row.logo_updated_at.timestamp())
        logo_url = f"/api/settings/logo/public?v={ts}"
    personio_has_credentials = (
        row.personio_client_id_enc is not None
        and row.personio_client_secret_enc is not None
    )
    return SettingsRead(
        color_primary=row.color_primary,
        color_accent=row.color_accent,
        color_background=row.color_background,
        color_foreground=row.color_foreground,
        color_muted=row.color_muted,
        color_destructive=row.color_destructive,
        app_name=row.app_name,
        logo_url=logo_url,
        logo_updated_at=row.logo_updated_at,
        personio_has_credentials=personio_has_credentials,
        personio_sync_interval_h=row.personio_sync_interval_h,
        personio_sick_leave_type_id=row.personio_sick_leave_type_id or [],
        personio_production_dept=row.personio_production_dept or [],
        personio_skill_attr_key=row.personio_skill_attr_key or [],
        target_overtime_ratio=float(row.target_overtime_ratio) if row.target_overtime_ratio is not None else None,
        target_sick_leave_ratio=float(row.target_sick_leave_ratio) if row.target_sick_leave_ratio is not None else None,
        target_fluctuation=float(row.target_fluctuation) if row.target_fluctuation is not None else None,
        target_revenue_per_employee=float(row.target_revenue_per_employee) if row.target_revenue_per_employee is not None else None,
        # Phase 39-02 — Sensor config read-only surfaces (columns exist since Phase 38 migration).
        # Admin write endpoints arrive in Phase 40 (SettingsUpdate unchanged here).
        sensor_poll_interval_s=row.sensor_poll_interval_s,
        sensor_temperature_min=row.sensor_temperature_min,
        sensor_temperature_max=row.sensor_temperature_max,
        sensor_humidity_min=row.sensor_humidity_min,
        sensor_humidity_max=row.sensor_humidity_max,
    )


def _etag_for(row: AppSettings) -> str:
    # Per Pitfall 4: one helper so response and comparison can't drift.
    assert row.logo_updated_at is not None
    return f'W/"{int(row.logo_updated_at.timestamp())}"'


# --- Handlers ------------------------------------------------------------

@router.get("", response_model=SettingsRead)
async def get_settings(db: AsyncSession = Depends(get_async_db_session)) -> SettingsRead:
    row = await _get_singleton(db)
    return _build_read(row)


@router.get("/personio-options", response_model=PersonioOptions)
async def get_personio_options(
    db: AsyncSession = Depends(get_async_db_session),
) -> PersonioOptions:
    """Fetch absence types and departments live from Personio (D-08, D-09).

    Returns degraded response (not 500) when credentials missing or API fails (D-10).
    """
    row = await _get_singleton(db)
    if not (row.personio_client_id_enc and row.personio_client_secret_enc):
        return PersonioOptions(
            absence_types=[],
            departments=[],
            skill_attributes=[],
            error="Personio-Zugangsdaten nicht konfiguriert",
        )
    try:
        client_id = decrypt_credential(row.personio_client_id_enc)
        client_secret = decrypt_credential(row.personio_client_secret_enc)
        client = PersonioClient(client_id=client_id, client_secret=client_secret)
        try:
            absence_types_raw = await client.fetch_absence_types()
            employees_raw = await client.fetch_employees()
        finally:
            await client.close()

        absence_types = []
        for t in absence_types_raw:
            try:
                attrs = t.get("attributes", {})
                type_id = attrs.get("id") if attrs.get("id") is not None else t.get("id")
                name = attrs.get("name") if isinstance(attrs.get("name"), str) else None
                if type_id is not None and name:
                    absence_types.append(AbsenceTypeOption(id=type_id, name=name))
            except (KeyError, TypeError):
                continue

        dept_names: set[str] = set()
        for e in employees_raw:
            dept = e.get("attributes", {}).get("department", {})
            val = dept.get("value") if isinstance(dept, dict) else None
            if isinstance(val, dict):
                name = val.get("attributes", {}).get("name")
            elif isinstance(val, str):
                name = val
            else:
                continue
            if name:
                dept_names.add(name)
        departments = sorted(dept_names)

        attr_keys: set[str] = set()
        for e in employees_raw:
            attrs = e.get("attributes", {})
            for key, val in attrs.items():
                if val is not None and val != "" and val != []:
                    attr_keys.add(key)
        skill_attributes = sorted(attr_keys)

        return PersonioOptions(
            absence_types=absence_types,
            departments=departments,
            skill_attributes=skill_attributes,
            error=None,
        )
    except PersonioAPIError as exc:
        return PersonioOptions(
            absence_types=[],
            departments=[],
            skill_attributes=[],
            error=str(exc),
        )


@router.put(
    "",
    response_model=SettingsRead,
    dependencies=[Depends(require_admin)],
)
async def put_settings(
    payload: SettingsUpdate,
    request: Request,
    db: AsyncSession = Depends(get_async_db_session),
) -> SettingsRead:
    row = await _get_singleton(db)

    row.color_primary = payload.color_primary
    row.color_accent = payload.color_accent
    row.color_background = payload.color_background
    row.color_foreground = payload.color_foreground
    row.color_muted = payload.color_muted
    row.color_destructive = payload.color_destructive
    row.app_name = payload.app_name

    # Personio credential guard — None means "don't change" (D-03, Pitfall 3)
    if payload.personio_client_id is not None:
        row.personio_client_id_enc = encrypt_credential(payload.personio_client_id)
    if payload.personio_client_secret is not None:
        row.personio_client_secret_enc = encrypt_credential(payload.personio_client_secret)

    # New Personio config fields — None means "don't change" (same pattern as credentials)
    if payload.personio_sync_interval_h is not None:
        row.personio_sync_interval_h = payload.personio_sync_interval_h
        # Reschedule APScheduler job immediately (D-06, D-07)
        sched = request.app.state.scheduler
        from app.scheduler import SYNC_JOB_ID, _run_scheduled_sync
        if payload.personio_sync_interval_h == 0:
            # manual-only: remove job if it exists (D-07)
            if sched.get_job(SYNC_JOB_ID):
                sched.remove_job(SYNC_JOB_ID)
        else:
            # Add with replace_existing=True handles both add and reschedule (Pitfall 1)
            sched.add_job(
                _run_scheduled_sync,
                trigger="interval",
                hours=payload.personio_sync_interval_h,
                id=SYNC_JOB_ID,
                replace_existing=True,
                max_instances=1,
            )
    if payload.personio_sick_leave_type_id is not None:
        row.personio_sick_leave_type_id = payload.personio_sick_leave_type_id
    if payload.personio_production_dept is not None:
        row.personio_production_dept = payload.personio_production_dept
    if payload.personio_skill_attr_key is not None:
        row.personio_skill_attr_key = payload.personio_skill_attr_key
    if payload.target_overtime_ratio is not None:
        row.target_overtime_ratio = payload.target_overtime_ratio
    if payload.target_sick_leave_ratio is not None:
        row.target_sick_leave_ratio = payload.target_sick_leave_ratio
    if payload.target_fluctuation is not None:
        row.target_fluctuation = payload.target_fluctuation
    if payload.target_revenue_per_employee is not None:
        row.target_revenue_per_employee = payload.target_revenue_per_employee

    # v1.15 Sensor Monitor — interval + global thresholds (Phase 40-01)
    if payload.sensor_poll_interval_s is not None:
        row.sensor_poll_interval_s = payload.sensor_poll_interval_s
        # Live reschedule — helper wraps its own try/except + log.exception
        # (Phase 38-03). Swallowing here is intentional: a broken reschedule
        # MUST NOT fail the PUT (per Phase 38 decision: "a broken PUT
        # /api/settings cannot leak scheduler internals").
        from app.scheduler import reschedule_sensor_poll
        try:
            reschedule_sensor_poll(payload.sensor_poll_interval_s)
        except Exception:  # noqa: BLE001 — defensive; helper already logs.
            pass
    if payload.sensor_temperature_min is not None:
        row.sensor_temperature_min = payload.sensor_temperature_min
    if payload.sensor_temperature_max is not None:
        row.sensor_temperature_max = payload.sensor_temperature_max
    if payload.sensor_humidity_min is not None:
        row.sensor_humidity_min = payload.sensor_humidity_min
    if payload.sensor_humidity_max is not None:
        row.sensor_humidity_max = payload.sensor_humidity_max

    # D-07: if the payload exactly matches canonical defaults, this is a
    # "reset to defaults" — also wipe the logo trio. A non-default PUT
    # (e.g. changing only app_name) preserves the logo.
    # Compare only the core settings fields (exclude Personio optional fields).
    _CORE_FIELDS = set(DEFAULT_SETTINGS.keys())
    if payload.model_dump(include=_CORE_FIELDS) == DEFAULT_SETTINGS:
        row.logo_data = None
        row.logo_mime = None
        row.logo_updated_at = None

    await db.commit()
    await db.refresh(row)
    return _build_read(row)


@router.post(
    "/logo",
    response_model=SettingsRead,
    dependencies=[Depends(require_admin)],
)
async def post_logo(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> SettingsRead:
    # 1. Extension allowlist (D-15) — case-insensitive
    filename = file.filename or ""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type: {filename}. Only .png and .svg allowed.",
        )

    # 2. Size enforcement (D-16) — don't trust Content-Length; read MAX+1
    raw = await file.read(MAX_LOGO_BYTES + 1)
    if len(raw) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=422, detail="Logo exceeds 1 MB size limit")

    # 3. MIME sniff (D-17) — never trust client-declared Content-Type
    try:
        mime = sniff_mime(raw, ext)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 4. SVG sanitization (D-12, D-13) — PNG skips nh3 (D-14)
    if ext == ".svg":
        try:
            raw = sanitize_svg(raw)
        except SvgRejected as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 5. Persist to singleton row
    row = await _get_singleton(db)
    row.logo_data = raw
    row.logo_mime = mime
    row.logo_updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    return _build_read(row)


@router.get("/logo")
async def get_logo(
    request: Request,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    row = await _get_singleton(db)
    if row.logo_data is None or row.logo_updated_at is None:
        raise HTTPException(status_code=404, detail="No logo set")

    etag = _etag_for(row)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})

    return Response(
        content=row.logo_data,
        media_type=row.logo_mime or "application/octet-stream",
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=31536000",  # ?v= query param busts it
        },
    )


@public_router.get("/logo/public")
async def get_logo_public(
    request: Request,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    row = await _get_singleton(db)
    if row.logo_data is None or row.logo_updated_at is None:
        raise HTTPException(status_code=404, detail="No logo set")
    etag = _etag_for(row)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        content=row.logo_data,
        media_type=row.logo_mime or "application/octet-stream",
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=300",
        },
    )
