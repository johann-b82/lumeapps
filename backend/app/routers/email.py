"""E-Mail API — v1.82 Office 365 background module.

All endpoints are admin-only (gated at the router level per the CLAUDE.md
"Auth gate placement" convention — no viewer-readable routes here).

Endpoints:
  POST /api/email/test  -> EmailSendResult  (send a probe mail to one address)
  POST /api/email/send  -> EmailSendResult  (generic send for reminders/reports)

Both return a uniform ``{ok, error}`` body: a failed send is a 200 with
``ok=false`` and a human-readable German error, not a 5xx — the admin UI shows
the message inline (same shape as the ATR fileserver /test endpoint).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.schemas import EmailSendRequest, EmailSendResult, EmailTestRequest
from app.security.directus_auth import get_current_user, require_admin
from app.services.email_service import (
    EmailError,
    EmailNotConfigured,
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
