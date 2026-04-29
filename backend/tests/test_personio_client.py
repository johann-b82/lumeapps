"""Unit tests for PersonioClient authentication and error handling.

All tests use mocked httpx responses — no live Personio account required.
"""
import time
import pytest
import httpx
from unittest.mock import AsyncMock, patch

from app.services.personio_client import (
    PersonioClient,
    PersonioAPIError,
    PersonioAuthError,
    PersonioRateLimitError,
    PersonioNetworkError,
)



def _make_client() -> PersonioClient:
    return PersonioClient(client_id="test_id", client_secret="test_secret")


def _mock_response(status_code: int, json_body: dict | None = None, headers: dict | None = None) -> httpx.Response:
    """Build a fake httpx.Response for mocking."""
    return httpx.Response(
        status_code=status_code,
        json=json_body or {},
        headers=headers or {},
    )


# ---------------------------------------------------------------------------
# authenticate() success path
# ---------------------------------------------------------------------------


async def test_authenticate_success():
    """POST /auth 200 → token returned and cached."""
    client = _make_client()
    mock_resp = _mock_response(
        200,
        json_body={"success": True, "data": {"token": "abc123"}},
    )
    with patch.object(client._http, "post", new=AsyncMock(return_value=mock_resp)):
        token = await client.authenticate()

    assert token == "abc123"
    assert client._token == "abc123"
    assert client._expires_at > time.monotonic()
    await client.close()


# ---------------------------------------------------------------------------
# authenticate() error paths
# ---------------------------------------------------------------------------


async def test_authenticate_invalid_credentials():
    """POST /auth 401 → PersonioAuthError raised."""
    client = _make_client()
    mock_resp = _mock_response(401)
    with patch.object(client._http, "post", new=AsyncMock(return_value=mock_resp)):
        with pytest.raises(PersonioAuthError) as exc_info:
            await client.authenticate()

    assert "Invalid credentials" in str(exc_info.value)
    await client.close()


async def test_authenticate_rate_limited():
    """POST /auth 429 → PersonioRateLimitError with retry_after=120."""
    client = _make_client()
    mock_resp = _mock_response(429, headers={"Retry-After": "120"})
    with patch.object(client._http, "post", new=AsyncMock(return_value=mock_resp)):
        with pytest.raises(PersonioRateLimitError) as exc_info:
            await client.authenticate()

    assert exc_info.value.retry_after == 120
    await client.close()


async def test_authenticate_timeout():
    """POST /auth timeout → PersonioNetworkError with 'timeout' in message."""
    client = _make_client()
    with patch.object(
        client._http,
        "post",
        new=AsyncMock(side_effect=httpx.TimeoutException("timeout")),
    ):
        with pytest.raises(PersonioNetworkError) as exc_info:
            await client.authenticate()

    assert "timeout" in str(exc_info.value).lower()
    await client.close()


async def test_authenticate_connection_error():
    """POST /auth ConnectError → PersonioNetworkError."""
    client = _make_client()
    with patch.object(
        client._http,
        "post",
        new=AsyncMock(side_effect=httpx.ConnectError("connection refused")),
    ):
        with pytest.raises(PersonioNetworkError):
            await client.authenticate()

    await client.close()


async def test_authenticate_server_error():
    """POST /auth 500 → PersonioAPIError with status_code=500."""
    client = _make_client()
    mock_resp = _mock_response(500)
    with patch.object(client._http, "post", new=AsyncMock(return_value=mock_resp)):
        with pytest.raises(PersonioAPIError) as exc_info:
            await client.authenticate()

    assert exc_info.value.status_code == 500
    await client.close()


# ---------------------------------------------------------------------------
# _get_valid_token() caching and refresh
# ---------------------------------------------------------------------------


async def test_get_valid_token_caches():
    """Token cached: second call to _get_valid_token() does NOT POST again."""
    client = _make_client()
    mock_resp = _mock_response(
        200,
        json_body={"success": True, "data": {"token": "cached_tok"}},
    )
    mock_post = AsyncMock(return_value=mock_resp)
    with patch.object(client._http, "post", new=mock_post):
        await client.authenticate()
        await client._get_valid_token()

    assert mock_post.call_count == 1
    await client.close()


async def test_get_valid_token_refreshes_when_expired():
    """Token expired (expires_at in the past) → _get_valid_token() re-authenticates."""
    client = _make_client()
    # Pre-seed a stale token
    client._token = "stale"
    client._expires_at = time.monotonic() - 1.0  # already expired

    mock_resp = _mock_response(
        200,
        json_body={"success": True, "data": {"token": "fresh_tok"}},
    )
    mock_post = AsyncMock(return_value=mock_resp)
    with patch.object(client._http, "post", new=mock_post):
        token = await client._get_valid_token()

    assert token == "fresh_tok"
    assert mock_post.call_count == 1
    await client.close()


async def test_get_valid_token_refreshes_within_buffer():
    """Token within 60s buffer → _get_valid_token() proactively re-authenticates."""
    client = _make_client()
    client._token = "almost_expired"
    client._expires_at = time.monotonic() + 30.0  # valid but within 60s buffer

    mock_resp = _mock_response(
        200,
        json_body={"success": True, "data": {"token": "refreshed_tok"}},
    )
    mock_post = AsyncMock(return_value=mock_resp)
    with patch.object(client._http, "post", new=mock_post):
        token = await client._get_valid_token()

    assert token == "refreshed_tok"
    assert mock_post.call_count == 1
    await client.close()


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


def test_exception_hierarchy():
    """All Personio exceptions are subclasses of PersonioAPIError."""
    assert issubclass(PersonioAuthError, PersonioAPIError)
    assert issubclass(PersonioRateLimitError, PersonioAPIError)
    assert issubclass(PersonioNetworkError, PersonioAPIError)


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


async def test_close():
    """close() shuts down the underlying httpx client."""
    client = _make_client()
    assert not client._http.is_closed
    await client.close()
    assert client._http.is_closed
