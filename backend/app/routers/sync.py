"""Sync API — PERS-02, PERS-04.

Endpoints:
  POST /api/sync       -> SyncResult (blocking full sync per D-01)
  POST /api/sync/test  -> SyncTestResult (credential test per D-17)
  GET  /api/sync/meta  -> SyncMetaRead (viewer-readable HR freshness)

Mixed gate (Phase B convention):
    Viewer-readable: GET /api/sync/meta
    Admin-only:      POST /api/sync, POST /api/sync/test
    Per-route ``Depends(require_admin)`` is used here because viewer reads
    and admin writes coexist on the same prefix (CLAUDE.md Conventions §
    "Auth dependencies live at the router level except mixed-gate routers").

Compute-justified: clause 1 (external Personio API call).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.security.directus_auth import get_current_user, require_admin
from app.models import AppSettings, PersonioSyncMeta
from app.schemas import SyncMetaRead, SyncResult, SyncTestResult
from app.security.fernet import decrypt_credential
from app.services.personio_client import (
    PersonioAPIError,
    PersonioAuthError,
    PersonioClient,
    PersonioNetworkError,
)

router = APIRouter(
    prefix="/api/sync",
    dependencies=[Depends(get_current_user)],
)


async def _get_credentials(db: AsyncSession) -> tuple[str, str]:
    """Read and decrypt Personio credentials from AppSettings."""
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    row = result.scalar_one_or_none()
    if row is None or not row.personio_client_id_enc or not row.personio_client_secret_enc:
        raise HTTPException(422, "Personio-Zugangsdaten nicht konfiguriert")
    client_id = decrypt_credential(row.personio_client_id_enc)
    client_secret = decrypt_credential(row.personio_client_secret_enc)
    return client_id, client_secret


@router.post(
    "",
    response_model=SyncResult,
    dependencies=[Depends(require_admin)],
)
async def run_sync(db: AsyncSession = Depends(get_async_db_session)) -> SyncResult:
    """Trigger a full Personio data sync (blocking, per D-01)."""
    from app.services import hr_sync

    # Verify credentials exist before starting sync
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    row = result.scalar_one_or_none()
    if row is None or not row.personio_client_id_enc or not row.personio_client_secret_enc:
        raise HTTPException(422, "Personio-Zugangsdaten nicht konfiguriert")

    try:
        return await hr_sync.run_sync(db)
    except PersonioAPIError as exc:
        return SyncResult(
            employees_synced=0,
            attendance_synced=0,
            absences_synced=0,
            status="error",
            error_message=str(exc),
        )


@router.post(
    "/test",
    response_model=SyncTestResult,
    dependencies=[Depends(require_admin)],
)
async def test_sync(db: AsyncSession = Depends(get_async_db_session)) -> SyncTestResult:
    """Test Personio credentials without syncing data (D-17)."""
    client_id, client_secret = await _get_credentials(db)
    client = PersonioClient(client_id=client_id, client_secret=client_secret)
    try:
        await client.authenticate()
        return SyncTestResult(success=True, error=None)
    except PersonioAuthError:
        return SyncTestResult(success=False, error="Ungueltige Zugangsdaten")
    except PersonioNetworkError as exc:
        return SyncTestResult(success=False, error=f"Personio nicht erreichbar: {exc}")
    except PersonioAPIError as exc:
        return SyncTestResult(success=False, error=str(exc))
    finally:
        await client.close()


@router.get("/meta", response_model=SyncMetaRead)
async def get_sync_meta(
    db: AsyncSession = Depends(get_async_db_session),
) -> SyncMetaRead:
    """Return personio_sync_meta singleton for HR freshness display."""
    result = await db.execute(
        select(PersonioSyncMeta).where(PersonioSyncMeta.id == 1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return SyncMetaRead()
    return SyncMetaRead.model_validate(row)
