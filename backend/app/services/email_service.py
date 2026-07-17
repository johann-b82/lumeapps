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
tab. Two send modes are supported and switchable there (``email_auth_mode``):

- ``app``: client-credentials (app-registration + ``Mail.Send`` application
  permission + admin consent), sends from ``email_sender_address``.
- ``delegated``: the admin signs in with their own M365 account via the
  device-code flow (self-consent, no admin needed) and mail is sent as that
  user. See ``begin_delegated_login`` / ``complete_delegated_login`` below.

See docs/modules/email.md for the connection contract and Azure setup.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSettings
from app.security.fernet import decrypt_credential, encrypt_credential
from app.services import graph_client
from app.services.graph_client import GraphAPIError, GraphMailClient


class EmailError(Exception):
    """Base class for e-mail service errors."""


class EmailNotConfigured(EmailError):
    """Raised when Office 365 credentials are missing or the module is disabled."""


class EmailSendError(EmailError):
    """Raised when the underlying transport (Graph) failed to send."""


@dataclass
class _AppConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    sender: str
    sender_name: str | None


@dataclass
class _DelegatedConfig:
    tenant_id: str
    client_id: str
    refresh_token: str
    account: str | None


async def is_configured(session: AsyncSession) -> bool:
    """Cheap check other modules can use before building a message.

    True when the module is enabled AND the active mode's credentials are present.
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
        session: an open AsyncSession (reads the settings row; in delegated mode
            also persists a rotated refresh token).
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

    if isinstance(cfg, _DelegatedConfig):
        client = GraphMailClient(
            tenant_id=cfg.tenant_id,
            client_id=cfg.client_id,
            mode="delegated",
            refresh_token=cfg.refresh_token,
        )
    else:
        client = GraphMailClient(
            tenant_id=cfg.tenant_id,
            client_id=cfg.client_id,
            client_secret=cfg.client_secret,
            sender=cfg.sender,
            sender_name=cfg.sender_name,
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
        # Persist a rotated delegated refresh token so the next send still works.
        if client.rotated_refresh_token and row is not None:
            row.email_delegated_refresh_token_enc = encrypt_credential(
                client.rotated_refresh_token
            )
            await session.commit()
        await client.close()


# ---------------------------------------------------------------------------
# Delegated (device-code) sign-in
# ---------------------------------------------------------------------------


async def begin_delegated_login(session: AsyncSession) -> dict:
    """Start the device-code flow. Returns the Microsoft device-code payload
    (``user_code``, ``verification_uri``, ``device_code``, ``interval``, ...).

    Requires tenant + client id to be saved first.
    """
    row = await _load_settings(session)
    if row is None or not (row.email_tenant_id and row.email_client_id):
        raise EmailNotConfigured(
            "Tenant-ID und Client-ID müssen zuerst gespeichert werden."
        )
    try:
        return await graph_client.start_device_code(row.email_tenant_id, row.email_client_id)
    except GraphAPIError as exc:
        raise EmailSendError(str(exc)) from exc


async def complete_delegated_login(session: AsyncSession, device_code: str) -> dict:
    """Poll the device-code flow once.

    Returns ``{"status": "pending"}``, ``{"status": "error", "error": ...}``, or
    ``{"status": "complete", "account": "<upn>"}``. On completion the refresh
    token is stored encrypted, the account recorded, and the mode switched to
    ``delegated``.
    """
    row = await _load_settings(session)
    if row is None or not (row.email_tenant_id and row.email_client_id):
        raise EmailNotConfigured(
            "Tenant-ID und Client-ID müssen zuerst gespeichert werden."
        )
    try:
        result = await graph_client.poll_device_code_once(
            row.email_tenant_id, row.email_client_id, device_code
        )
    except GraphAPIError as exc:
        raise EmailSendError(str(exc)) from exc

    if result.get("status") != "complete":
        return result

    refresh_token = result.get("refresh_token")
    if not refresh_token:
        return {"status": "error", "error": "Kein Refresh-Token erhalten (offline_access?)."}
    account = await graph_client.fetch_delegated_account(result["access_token"])
    row.email_delegated_refresh_token_enc = encrypt_credential(refresh_token)
    row.email_delegated_account = account
    row.email_auth_mode = "delegated"
    await session.commit()
    return {"status": "complete", "account": account}


async def disconnect_delegated(session: AsyncSession) -> None:
    """Forget the delegated sign-in (clear token + account)."""
    row = await _load_settings(session)
    if row is None:
        return
    row.email_delegated_refresh_token_enc = None
    row.email_delegated_account = None
    await session.commit()


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


async def _load_settings(session: AsyncSession) -> AppSettings | None:
    return (
        await session.execute(select(AppSettings).where(AppSettings.id == 1))
    ).scalar_one_or_none()


def _config_from_row(
    row: AppSettings | None,
) -> _AppConfig | _DelegatedConfig | None:
    """Return the active-mode config, or None if disabled/incomplete."""
    if row is None or not row.email_enabled:
        return None
    if not (row.email_tenant_id and row.email_client_id):
        return None

    if row.email_auth_mode == "delegated":
        if row.email_delegated_refresh_token_enc is None:
            return None
        return _DelegatedConfig(
            tenant_id=row.email_tenant_id,
            client_id=row.email_client_id,
            refresh_token=decrypt_credential(row.email_delegated_refresh_token_enc),
            account=row.email_delegated_account,
        )

    # app (client-credentials) mode
    if not (row.email_client_secret_enc is not None and row.email_sender_address):
        return None
    return _AppConfig(
        tenant_id=row.email_tenant_id,
        client_id=row.email_client_id,
        client_secret=decrypt_credential(row.email_client_secret_enc),
        sender=row.email_sender_address,
        sender_name=row.email_sender_name,
    )


def _as_list(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else list(value)
