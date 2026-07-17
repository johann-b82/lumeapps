"""Shared e-mail background service — the module every other module connects to.

This is the single, app-wide entry point for sending mail (reminders, reports,
notifications). Any router or service can import ``send_email`` and hand it a
recipient, subject and body; configuration and transport are handled here.

    from app.services.email_service import send_email, EmailNotConfigured

    await send_email(
        session,
        to="team@firma.de",
        subject="Wöchentlicher KPI-Bericht",
        body_html="<h1>...</h1>",
    )

Configuration lives on the ``AppSettings`` singleton (Office 365 / Microsoft
Graph credentials + sender identity), managed in the admin settings "E-Mail"
tab. See docs/modules/email.md for the connection contract and Azure setup.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSettings
from app.security.fernet import decrypt_credential
from app.services.graph_client import (
    GraphAPIError,
    GraphMailClient,
)


class EmailError(Exception):
    """Base class for e-mail service errors."""


class EmailNotConfigured(EmailError):
    """Raised when Office 365 credentials are missing or the module is disabled."""


class EmailSendError(EmailError):
    """Raised when the underlying transport (Graph) failed to send."""


async def is_configured(session: AsyncSession) -> bool:
    """Cheap check other modules can use before building a message.

    True when the module is enabled AND all required credentials are present.
    """
    row = await _load_settings(session)
    return _config_from_row(row) is not None


async def send_email(
    session: AsyncSession,
    *,
    to: str | list[str],
    subject: str,
    body_html: str,
    body_text: str | None = None,
    cc: str | list[str] | None = None,
) -> None:
    """Send an e-mail via the configured Office 365 account.

    Args:
        session: an open AsyncSession (used only to read the settings row).
        to: one address or a list of addresses.
        subject: message subject.
        body_html: HTML body (also used as the text body if that's all you have).
        body_text: optional plain-text alternative.
        cc: optional carbon-copy address(es).

    Raises:
        EmailNotConfigured: module disabled or credentials incomplete.
        EmailSendError: Graph rejected the message or was unreachable.
    """
    row = await _load_settings(session)
    cfg = _config_from_row(row)
    if cfg is None:
        raise EmailNotConfigured(
            "E-Mail-Modul ist nicht konfiguriert oder deaktiviert "
            "(Admin → Einstellungen → E-Mail)."
        )

    tenant_id, client_id, client_secret, sender, sender_name = cfg
    client = GraphMailClient(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        sender=sender,
        sender_name=sender_name,
    )
    try:
        await client.send_mail(
            to=_as_list(to),
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            cc=_as_list(cc) if cc else None,
        )
    except GraphAPIError as exc:
        raise EmailSendError(str(exc)) from exc
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


async def _load_settings(session: AsyncSession) -> AppSettings | None:
    return (
        await session.execute(select(AppSettings).where(AppSettings.id == 1))
    ).scalar_one_or_none()


def _config_from_row(
    row: AppSettings | None,
) -> tuple[str, str, str, str, str | None] | None:
    """Return (tenant, client_id, secret, sender, sender_name) or None.

    None when the module is disabled or any required field/secret is missing.
    """
    if row is None or not row.email_enabled:
        return None
    if not (
        row.email_tenant_id
        and row.email_client_id
        and row.email_client_secret_enc is not None
        and row.email_sender_address
    ):
        return None
    secret = decrypt_credential(row.email_client_secret_enc)
    return (
        row.email_tenant_id,
        row.email_client_id,
        secret,
        row.email_sender_address,
        row.email_sender_name,
    )


def _as_list(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else list(value)
