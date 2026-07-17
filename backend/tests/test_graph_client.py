"""Unit tests for GraphMailClient — mocked httpx, no live Office 365 account."""
import time

import httpx
import pytest
from unittest.mock import AsyncMock, patch

from app.services.graph_client import (
    GraphAuthError,
    GraphMailClient,
    GraphNetworkError,
    GraphSendError,
    poll_device_code_once,
    start_device_code,
)


def _client() -> GraphMailClient:
    return GraphMailClient(
        tenant_id="t", client_id="c", client_secret="s", sender="from@firma.de"
    )


def _resp(status_code: int, json_body: dict | None = None) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=json_body or {})


async def test_authenticate_success_caches_token():
    c = _client()
    mock = _resp(200, {"access_token": "tok", "expires_in": 3600})
    with patch.object(c._http, "post", new=AsyncMock(return_value=mock)):
        tok = await c._get_valid_token()
    assert tok == "tok"
    assert c._token == "tok"
    assert c._expires_at > time.monotonic()
    await c.close()


async def test_authenticate_bad_credentials_raises_auth_error():
    c = _client()
    mock = _resp(401, {"error": "invalid_client", "error_description": "bad secret"})
    with patch.object(c._http, "post", new=AsyncMock(return_value=mock)):
        with pytest.raises(GraphAuthError) as exc:
            await c._get_valid_token()
    assert "bad secret" in str(exc.value)
    await c.close()


async def test_send_mail_success_202():
    c = _client()
    c._token = "tok"
    c._expires_at = time.monotonic() + 3600
    with patch.object(c._http, "post", new=AsyncMock(return_value=_resp(202))) as post:
        await c.send_mail(to=["a@firma.de"], subject="Hi", body_html="<p>x</p>")
    # sendMail URL targets the configured sender mailbox.
    assert "users/from@firma.de/sendMail" in post.call_args.args[0]
    await c.close()


async def test_send_mail_403_raises_send_error():
    c = _client()
    c._token = "tok"
    c._expires_at = time.monotonic() + 3600
    mock = _resp(403, {"error": {"message": "Access denied"}})
    with patch.object(c._http, "post", new=AsyncMock(return_value=mock)):
        with pytest.raises(GraphSendError):
            await c.send_mail(to=["a@firma.de"], subject="Hi", body_html="<p>x</p>")
    await c.close()


async def test_network_error_on_timeout():
    c = _client()
    with patch.object(
        c._http, "post", new=AsyncMock(side_effect=httpx.TimeoutException("boom"))
    ):
        with pytest.raises(GraphNetworkError):
            await c._get_valid_token()
    await c.close()


# --- Delegated (device-code) mode ------------------------------------------


async def test_delegated_send_uses_me_endpoint_and_rotates_token():
    c = GraphMailClient(
        tenant_id="t", client_id="c", mode="delegated", refresh_token="old-rt"
    )
    token_resp = _resp(200, {"access_token": "at", "refresh_token": "new-rt", "expires_in": 3600})
    send_resp = _resp(202)
    with patch.object(
        c._http, "post", new=AsyncMock(side_effect=[token_resp, send_resp])
    ) as post:
        await c.send_mail(to=["a@firma.de"], subject="Hi", body_html="<p>x</p>")
    # Delegated send targets /me/sendMail, not /users/{sender}.
    assert "/me/sendMail" in post.call_args_list[1].args[0]
    # Rotated refresh token surfaced for the caller to persist.
    assert c.rotated_refresh_token == "new-rt"
    await c.close()


async def test_start_device_code_returns_payload():
    payload = {
        "device_code": "dc", "user_code": "ABCD-EFGH",
        "verification_uri": "https://microsoft.com/devicelogin",
        "expires_in": 900, "interval": 5, "message": "go",
    }
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=_resp(200, payload))):
        out = await start_device_code("t", "c")
    assert out["user_code"] == "ABCD-EFGH"


async def test_poll_pending_then_complete():
    pending = httpx.Response(400, json={"error": "authorization_pending"})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=pending)):
        r = await poll_device_code_once("t", "c", "dc")
    assert r["status"] == "pending"

    done = _resp(200, {"access_token": "at", "refresh_token": "rt", "expires_in": 3600})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=done)):
        r = await poll_device_code_once("t", "c", "dc")
    assert r["status"] == "complete"
    assert r["refresh_token"] == "rt"


async def test_poll_error_declined():
    declined = httpx.Response(400, json={"error": "expired_token", "error_description": "expired"})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=declined)):
        r = await poll_device_code_once("t", "c", "dc")
    assert r["status"] == "error"
    assert "expired" in r["error"]
