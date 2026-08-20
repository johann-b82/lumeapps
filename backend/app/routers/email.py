"""E-Mail API — v1.83 Office 365 background module.

All endpoints are admin-only (gated at the router level per the CLAUDE.md
"Auth gate placement" convention — no viewer-readable routes here).

Endpoints:
  POST /api/email/test  -> EmailSendResult  (send a probe mail to one address)
  POST /api/email/send  -> EmailSendResult  (generic send for reminders/reports)

Both return a uniform ``{ok, error}`` body: a failed send is a 200 with
``ok=false`` and a human-readable German error, not a 5xx — the admin UI shows
the message inline (same shape as the ATR fileserver /test endpoint).

Compute-justified: clause 1 (side effect outside Postgres) — these routes
talk to Office 365 over Graph/SMTP and hold the delegated-auth flow; nothing
here maps onto a Directus collection read or write.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException

from app.database import get_async_db_session
from app.schemas import (
    DeviceCodePollRequest,
    DeviceCodePollResult,
    DeviceCodeStart,
    EmailSendRequest,
    EmailSendResult,
    EmailTestRequest,
)
from app.security.directus_auth import get_current_user, require_admin
from app.services.email_service import (
    EmailError,
    EmailNotConfigured,
    begin_delegated_login,
    complete_delegated_login,
    disconnect_delegated,
    send_email,
)

router = APIRouter(
    prefix="/api/email",
    tags=["email"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)


@router.post("/test", response_model=EmailSendResult)
async def email_test(
    payload: EmailTestRequest,
    db: AsyncSession = Depends(get_async_db_session),
) -> EmailSendResult:
    """Send a fixed probe message so the admin can verify the O365 setup."""
    try:
        await send_email(
            db,
            to=payload.to,
            subject="LumeApps — Test-E-Mail",
            body_html=(
                "<p>Dies ist eine Test-E-Mail aus LumeApps.</p>"
                "<p>Wenn du sie erhältst, ist die Office-365-Anbindung "
                "korrekt konfiguriert.</p>"
            ),
        )
    except EmailNotConfigured as exc:
        return EmailSendResult(ok=False, error=str(exc))
    except EmailError as exc:
        return EmailSendResult(ok=False, error=str(exc))
    return EmailSendResult(ok=True, error=None)


# --- Delegated (device-code) sign-in ---------------------------------------


@router.post("/delegated/start", response_model=DeviceCodeStart)
async def delegated_start(
    db: AsyncSession = Depends(get_async_db_session),
) -> DeviceCodeStart:
    """Begin device-code sign-in. Admin opens the URL and enters the code."""
    try:
        payload = await begin_delegated_login(db)
    except EmailError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DeviceCodeStart(
        device_code=payload["device_code"],
        user_code=payload["user_code"],
        verification_uri=payload.get("verification_uri") or payload.get("verification_url", ""),
        expires_in=int(payload.get("expires_in", 900)),
        interval=int(payload.get("interval", 5)),
        message=payload.get("message", ""),
    )


@router.post("/delegated/poll", response_model=DeviceCodePollResult)
async def delegated_poll(
    payload: DeviceCodePollRequest,
    db: AsyncSession = Depends(get_async_db_session),
) -> DeviceCodePollResult:
    """Poll once for completion of the device-code sign-in."""
    try:
        result = await complete_delegated_login(db, payload.device_code)
    except EmailError as exc:
        return DeviceCodePollResult(status="error", error=str(exc))
    return DeviceCodePollResult(
        status=result["status"],
        account=result.get("account"),
        error=result.get("error"),
    )


@router.post("/delegated/disconnect", response_model=EmailSendResult)
async def delegated_disconnect(
    db: AsyncSession = Depends(get_async_db_session),
) -> EmailSendResult:
    """Forget the delegated sign-in (clear stored token + account)."""
    await disconnect_delegated(db)
    return EmailSendResult(ok=True, error=None)


@router.post("/send", response_model=EmailSendResult)
async def email_send(
    payload: EmailSendRequest,
    db: AsyncSession = Depends(get_async_db_session),
) -> EmailSendResult:
    """Generic send surface for reminders and reports."""
    try:
        await send_email(
            db,
            to=[str(a) for a in payload.to],
            subject=payload.subject,
            body_html=payload.body_html,
            body_text=payload.body_text,
            cc=[str(a) for a in payload.cc] if payload.cc else None,
        )
    except EmailNotConfigured as exc:
        return EmailSendResult(ok=False, error=str(exc))
    except EmailError as exc:
        return EmailSendResult(ok=False, error=str(exc))
    return EmailSendResult(ok=True, error=None)
