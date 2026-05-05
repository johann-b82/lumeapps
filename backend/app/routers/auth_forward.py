"""Caddy forward_auth endpoint — gates Paperless-ngx behind Directus session.

Caddy is configured to forward every request that lands on `/paperless/*`
through this endpoint first (caddy/Caddyfile). When the cookie attached to
the inbound request resolves to a valid Directus user, we return 200 and
emit `X-Remote-User: <email>`; Caddy lifts that header onto the upstream
request to the Paperless container, which has
`PAPERLESS_ENABLE_HTTP_REMOTE_USER=true` and auto-provisions a local user
matching the header on first hit.

The endpoint is mounted at `/api/auth/forward` and is intentionally
public (no Depends(get_current_user)) — Caddy's auth call is itself
unauthenticated; this code IS the authentication.

Two networking notes:
  1. Container DNS: this code is in the `api` container, Directus is at
     `directus:8055` over the Compose network. We never call Directus via
     the public Caddy URL — that would loop the request through forward_auth
     again.
  2. Cookie scope: the SPA logs into Directus same-origin via Caddy's
     `/directus/*` route, so the `directus_refresh_token` cookie is set on
     the top-level origin and is automatically attached to `/paperless/*`
     requests too. We forward the inbound `Cookie` header verbatim to
     Directus's `/auth/refresh` endpoint to validate it.

A small in-memory cache (60s TTL) keyed on the cookie hash dedupes the
many static-asset requests Paperless fires per page so we don't hammer
Directus's `/auth/refresh` (which rotates tokens on every call).
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Header, Response, status

from app.config import settings as app_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

_logger = logging.getLogger(__name__)

# In-process cookie -> (email, expires_at). 60s TTL is short enough that
# revoking a Directus session takes effect within a minute, long enough
# that loading a Paperless page (~30 static asset hits) only triggers
# one Directus call.
_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_TTL_S = 60.0
_CACHE_MAX_ENTRIES = 256

# Internal Directus URL — Compose-network DNS name, not the public Caddy URL.
_DIRECTUS_INTERNAL_URL = "http://directus:8055"


def _cookie_key(cookie_header: str) -> str:
    return hashlib.sha256(cookie_header.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Optional[str]:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    email, exp = entry
    if exp < time.time():
        _CACHE.pop(key, None)
        return None
    return email


def _cache_put(key: str, email: str) -> None:
    if len(_CACHE) >= _CACHE_MAX_ENTRIES:
        # Drop the oldest entry to keep memory bounded under load.
        oldest = min(_CACHE.items(), key=lambda kv: kv[1][1])[0]
        _CACHE.pop(oldest, None)
    _CACHE[key] = (email, time.time() + _CACHE_TTL_S)


@router.get("/forward", include_in_schema=False)
async def forward_auth(
    response: Response,
    cookie: str | None = Header(default=None, alias="Cookie"),
) -> Response:
    """Validate the inbound request's Directus session and emit Remote-User.

    Caddy hits this endpoint with the original request's headers (including
    Cookie). On 200 with a `X-Remote-User` header, Caddy proxies the
    request to Paperless with that header attached. On 401, Caddy short-
    circuits with the same status — the user sees Paperless's login page
    only via Directus.
    """
    if not cookie or "directus_" not in cookie:
        # Fast path: no Directus cookie at all; no point calling /auth/refresh.
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response

    key = _cookie_key(cookie)
    cached = _cache_get(key)
    if cached is not None:
        response.headers["X-Remote-User"] = cached
        response.status_code = status.HTTP_200_OK
        return response

    # /auth/refresh in cookie mode reads the refresh-token cookie, rotates
    # it, and returns a fresh access_token. We then call /users/me with that
    # access_token to resolve the email — readMe doesn't need a body and is
    # cheap. We could decode the JWT directly, but emails aren't in the
    # token payload (only `id` + `role`).
    try:
        async with httpx.AsyncClient(
            base_url=_DIRECTUS_INTERNAL_URL, timeout=5.0
        ) as client:
            refresh = await client.post(
                "/auth/refresh",
                headers={"Cookie": cookie, "Content-Type": "application/json"},
                json={"mode": "cookie"},
            )
            if refresh.status_code != 200:
                response.status_code = status.HTTP_401_UNAUTHORIZED
                return response
            access_token = refresh.json().get("data", {}).get("access_token")
            if not access_token:
                response.status_code = status.HTTP_401_UNAUTHORIZED
                return response
            me = await client.get(
                "/users/me",
                params={"fields": "id,email"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if me.status_code != 200:
                response.status_code = status.HTTP_401_UNAUTHORIZED
                return response
            email = me.json().get("data", {}).get("email")
            if not email:
                response.status_code = status.HTTP_401_UNAUTHORIZED
                return response
    except httpx.HTTPError:
        # Network error reaching Directus — fail closed.
        _logger.exception("forward_auth: directus call failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response

    _cache_put(key, email)
    response.headers["X-Remote-User"] = email
    response.status_code = status.HTTP_200_OK
    # Use the env-validated SECRET via app_settings to ensure the api
    # container is properly configured at boot — keeps a runtime
    # dependency on DIRECTUS_SECRET so misconfigured deploys fail loud.
    _ = app_settings.DIRECTUS_SECRET
    return response
