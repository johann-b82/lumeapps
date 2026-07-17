"""Async Microsoft Graph mail client (Office 365) — client-credentials flow.

This is the single integration point with Microsoft Graph for sending e-mail.
The shared e-mail service (``app/services/email_service.py``) builds an instance
from the Office 365 credentials stored on the ``AppSettings`` singleton and calls
``send_mail``.

Auth model: OAuth 2.0 client credentials (application permission ``Mail.Send``).
The Azure/Entra app registration must have that permission granted with admin
consent. No SMTP, no user password — see docs/modules/email.md for setup.

Decisions (mirrors personio_client.py conventions):
  - Custom exception hierarchy with user-facing messages (GraphAuthError, ...).
  - Token cached in-memory with a refresh buffer; lost on container restart.
"""
from __future__ import annotations

import time

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AUTHORITY_BASE = "https://login.microsoftonline.com"
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
TOKEN_REFRESH_BUFFER = 60  # re-auth if <60s remaining


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class GraphAPIError(Exception):
    """Base class for all Graph client errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GraphAuthError(GraphAPIError):
    """Raised on token acquisition failure (bad tenant/client id/secret, consent)."""


class GraphSendError(GraphAPIError):
    """Raised when Graph rejects the sendMail request (permissions, bad sender)."""


class GraphNetworkError(GraphAPIError):
    """Raised on timeout or connection failure — Graph unreachable."""


# ---------------------------------------------------------------------------
# GraphMailClient
# ---------------------------------------------------------------------------


class GraphMailClient:
    """Async client that sends mail via ``/users/{sender}/sendMail``.

    Usage:
        client = GraphMailClient(tenant_id, client_id, client_secret, sender)
        try:
            await client.send_mail(to=[...], subject="...", body_html="...")
        finally:
            await client.close()
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        sender: str,
        sender_name: str | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._sender = sender
        self._sender_name = sender_name
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._http = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self._http.aclose()

    # --- Auth --------------------------------------------------------------

    async def _authenticate(self) -> str:
        url = f"{AUTHORITY_BASE}/{self._tenant_id}/oauth2/v2.0/token"
        try:
            resp = await self._http.post(
                url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "scope": GRAPH_SCOPE,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.TimeoutException as exc:
            raise GraphNetworkError(f"Microsoft Graph unreachable (timeout): {exc}") from exc
        except httpx.RequestError as exc:
            raise GraphNetworkError(f"Microsoft Graph unreachable: {exc}") from exc

        if resp.is_error:
            # The token endpoint returns a JSON body with error_description on
            # failure — surface it so the admin can act (wrong secret, no consent).
            detail = _extract_error(resp)
            raise GraphAuthError(
                f"Token-Anforderung fehlgeschlagen (HTTP {resp.status_code}): {detail}",
                status_code=resp.status_code,
            )

        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise GraphAuthError("Token-Antwort ohne access_token")
        expires_in = int(data.get("expires_in", 3600))
        self._token = token
        self._expires_at = time.monotonic() + expires_in
        return token

    async def _get_valid_token(self) -> str:
        if (
            self._token is None
            or time.monotonic() > self._expires_at - TOKEN_REFRESH_BUFFER
        ):
            await self._authenticate()
        assert self._token is not None
        return self._token

    # --- Send --------------------------------------------------------------

    async def send_mail(
        self,
        *,
        to: list[str],
        subject: str,
        body_html: str,
        body_text: str | None = None,
        cc: list[str] | None = None,
        save_to_sent_items: bool = True,
    ) -> None:
        """POST /users/{sender}/sendMail. Raises GraphSendError on failure.

        Body is sent as HTML by default. ``body_text`` is accepted for API
        symmetry; when only text is given it is used as the HTML content
        (Graph has a single contentType per message).
        """
        token = await self._get_valid_token()
        content = body_html if body_html else (body_text or "")

        def _recipients(addrs: list[str]) -> list[dict]:
            return [{"emailAddress": {"address": a}} for a in addrs]

        message: dict = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": content},
            "toRecipients": _recipients(to),
        }
        if cc:
            message["ccRecipients"] = _recipients(cc)
        if self._sender_name:
            message["from"] = {
                "emailAddress": {"address": self._sender, "name": self._sender_name}
            }

        url = f"{GRAPH_BASE_URL}/users/{self._sender}/sendMail"
        try:
            resp = await self._http.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"message": message, "saveToSentItems": save_to_sent_items},
            )
        except httpx.TimeoutException as exc:
            raise GraphNetworkError(f"Microsoft Graph unreachable (timeout): {exc}") from exc
        except httpx.RequestError as exc:
            raise GraphNetworkError(f"Microsoft Graph unreachable: {exc}") from exc

        # sendMail returns 202 Accepted with an empty body on success.
        if resp.status_code == 202:
            return
        if resp.status_code in (401, 403):
            raise GraphSendError(
                "Versand abgelehnt — fehlende 'Mail.Send'-Berechtigung/Consent "
                f"oder unbekannter Absender ({_extract_error(resp)})",
                status_code=resp.status_code,
            )
        raise GraphSendError(
            f"Graph sendMail fehlgeschlagen (HTTP {resp.status_code}): {_extract_error(resp)}",
            status_code=resp.status_code,
        )


def _extract_error(resp: httpx.Response) -> str:
    """Best-effort extraction of a human-readable error from a Graph response."""
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001 — non-JSON error body
        return resp.text[:200] if resp.text else "(no body)"
    if isinstance(data, dict):
        if "error_description" in data:  # token endpoint shape
            return str(data["error_description"]).splitlines()[0][:200]
        err = data.get("error")
        if isinstance(err, dict) and "message" in err:  # graph resource shape
            return str(err["message"])[:200]
        if isinstance(err, str):
            return err[:200]
    return str(data)[:200]
