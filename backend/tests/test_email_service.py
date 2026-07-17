"""Coverage for the shared e-mail service (config gating + send delegation)."""
import pytest
from unittest.mock import AsyncMock, patch

from app.database import AsyncSessionLocal
from app.services.email_service import (
    EmailNotConfigured,
    complete_delegated_login,
    is_configured,
    send_email,
)

_CORE = [
    "color_primary", "color_accent", "color_background",
    "color_foreground", "color_muted", "color_destructive", "app_name",
]


async def _configure(admin_client, *, enabled: bool, mode: str = "app") -> None:
    base = (await admin_client.get("/api/settings")).json()
    payload = {k: base[k] for k in _CORE}
    payload.update(
        email_tenant_id="t", email_client_id="c", email_client_secret="s",
        email_sender_address="from@firma.de", email_sender_name="Lume",
        email_enabled=enabled, email_auth_mode=mode,
    )
    r = await admin_client.put("/api/settings", json=payload)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_not_configured_when_disabled(admin_client):
    await _configure(admin_client, enabled=False)
    async with AsyncSessionLocal() as session:
        assert await is_configured(session) is False
        with pytest.raises(EmailNotConfigured):
            await send_email(session, to="x@firma.de", subject="s", body_html="<p>x</p>")


@pytest.mark.asyncio
async def test_send_delegates_to_graph_client(admin_client):
    await _configure(admin_client, enabled=True)
    instance = AsyncMock()
    instance.rotated_refresh_token = None
    with patch("app.services.email_service.GraphMailClient", return_value=instance) as ctor:
        async with AsyncSessionLocal() as session:
            assert await is_configured(session) is True
            await send_email(
                session,
                to="x@firma.de",
                subject="Betreff",
                body_html="<p>hallo</p>",
                cc=["y@firma.de"],
            )
    # Built with the decrypted credentials from settings.
    kwargs = ctor.call_args.kwargs
    assert kwargs["tenant_id"] == "t"
    assert kwargs["client_secret"] == "s"
    assert kwargs["sender"] == "from@firma.de"
    # Delegated send + always closed.
    instance.send_mail.assert_awaited_once()
    sent = instance.send_mail.await_args.kwargs
    assert sent["to"] == ["x@firma.de"]
    assert sent["cc"] == ["y@firma.de"]
    assert sent["subject"] == "Betreff"
    instance.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_delegated_login_persists_token_and_switches_mode(admin_client):
    """A completed device-code login stores the refresh token, records the
    account, and flips the mode to 'delegated'."""
    # Save tenant/client (required before login).
    base = (await admin_client.get("/api/settings")).json()
    payload = {k: base[k] for k in _CORE}
    payload.update(email_tenant_id="t", email_client_id="c")
    await admin_client.put("/api/settings", json=payload)

    poll_ok = {"status": "complete", "access_token": "at", "refresh_token": "rt", "expires_in": 3600}
    with patch("app.services.email_service.graph_client.poll_device_code_once",
               new=AsyncMock(return_value=poll_ok)), \
         patch("app.services.email_service.graph_client.fetch_delegated_account",
               new=AsyncMock(return_value="me@firma.de")):
        async with AsyncSessionLocal() as session:
            result = await complete_delegated_login(session, "dc")
    assert result["status"] == "complete"
    assert result["account"] == "me@firma.de"

    body = (await admin_client.get("/api/settings")).json()
    assert body["email_auth_mode"] == "delegated"
    assert body["email_delegated_account"] == "me@firma.de"
    assert body["email_delegated_connected"] is True


@pytest.mark.asyncio
async def test_delegated_mode_dispatches_me_send(admin_client):
    """In delegated mode send_email builds a delegated GraphMailClient."""
    await _configure(admin_client, enabled=True, mode="delegated")
    # Store a delegated refresh token by completing a mocked login.
    base = (await admin_client.get("/api/settings")).json()
    payload = {k: base[k] for k in _CORE}
    payload.update(email_tenant_id="t", email_client_id="c")
    await admin_client.put("/api/settings", json=payload)
    poll_ok = {"status": "complete", "access_token": "at", "refresh_token": "rt", "expires_in": 3600}
    with patch("app.services.email_service.graph_client.poll_device_code_once",
               new=AsyncMock(return_value=poll_ok)), \
         patch("app.services.email_service.graph_client.fetch_delegated_account",
               new=AsyncMock(return_value="me@firma.de")):
        async with AsyncSessionLocal() as session:
            await complete_delegated_login(session, "dc")

    instance = AsyncMock()
    instance.rotated_refresh_token = None
    with patch("app.services.email_service.GraphMailClient", return_value=instance) as ctor:
        async with AsyncSessionLocal() as session:
            await send_email(session, to="x@firma.de", subject="s", body_html="<p>x</p>")
    kwargs = ctor.call_args.kwargs
    assert kwargs["mode"] == "delegated"
    assert kwargs["refresh_token"] == "rt"
    instance.send_mail.assert_awaited_once()
