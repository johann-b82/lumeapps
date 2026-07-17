"""Coverage for the shared e-mail service (config gating + send delegation)."""
import pytest
from unittest.mock import AsyncMock, patch

from app.database import AsyncSessionLocal
from app.services.email_service import (
    EmailNotConfigured,
    is_configured,
    send_email,
)

_CORE = [
    "color_primary", "color_accent", "color_background",
    "color_foreground", "color_muted", "color_destructive", "app_name",
]


async def _configure(admin_client, *, enabled: bool) -> None:
    base = (await admin_client.get("/api/settings")).json()
    payload = {k: base[k] for k in _CORE}
    payload.update(
        email_tenant_id="t", email_client_id="c", email_client_secret="s",
        email_sender_address="from@firma.de", email_sender_name="Lume",
        email_enabled=enabled,
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
