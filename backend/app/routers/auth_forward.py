"""Caddy forward_auth endpoint — gates embedded apps behind Directus session.

Caddy is configured to forward every request that lands on `/paperless/*`,
`/pdf/*`, and `/op/*` through this endpoint first (caddy/Caddyfile). When
the Directus session cookie attached to the inbound request is valid, we
return 200 and emit `X-Remote-User: <email>`; Caddy lifts that header onto
the upstream request. On 401 the auth status short-circuits to the client
and the user sees the SPA login screen.

The endpoint is mounted at `/api/auth/forward` and is intentionally public
(no Depends(get_current_user)) — Caddy's auth call is itself unauthenticated;
this code IS the authentication.

Why JWT decode and not /auth/refresh?
  Directus 11 in `mode: session` sets a `directus_session_token` cookie that
  is itself an HS256 JWT signed with the same `DIRECTUS_SECRET` we already
  carry in app config (see app/config.py). Verifying the JWT locally avoids
  every problem the previous `/auth/refresh`-based implementation had:
    * No refresh-token rotation race with the SPA's own refresh loop. The
      JWT is read-only here; Directus is never called on the hot path, so
      forward_auth never invalidates the SPA's session.
    * No 60s freshness window — the JWT's own `exp` claim is the source of
      truth, refreshed naturally by the SPA via /auth/refresh on a normal
      lifecycle.
    * No EOF / KeyError races (the v1.47 fix that explicitly set
      `status_code=200` is preserved by always returning a fully-formed
      Response below).

Email lookup: the JWT payload exposes `id` + `role` but NOT `email`. We
keep an in-memory `id -> email` cache populated lazily via a single
`/users/me` Bearer call against Directus's internal URL on first hit per
session. The session JWT itself is the access token in session mode, so
the Bearer call needs no /auth/refresh.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional

import httpx
import jwt
from fastapi import APIRouter, Header, Response, status

from app.config import settings as app_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

_logger = logging.getLogger(__name__)

# Directus 11 session-mode cookie. Set by the SPA's `authentication("session")`
# call (frontend/src/lib/directusClient.ts). HS256-signed by DIRECTUS_SECRET.
_SESSION_COOKIE_RE = re.compile(r"(?:^|;\s*)directus_session_token=([^;]+)")

# id -> (email, fetched_at). 5min TTL. Bounded under load.
_EMAIL_CACHE: dict[str, tuple[str, float]] = {}
_EMAIL_CACHE_TTL_S = 300.0
_EMAIL_CACHE_MAX_ENTRIES = 512

# Internal Directus URL — Compose-network DNS name, not the public Caddy URL.
_DIRECTUS_INTERNAL_URL = "http://directus:8055"


def _extract_session_token(cookie_header: str) -> Optional[str]:
    m = _SESSION_COOKIE_RE.search(cookie_header)
    return m.group(1) if m else None


def _cache_get_email(user_id: str) -> Optional[str]:
    entry = _EMAIL_CACHE.get(user_id)
    if entry is None:
        return None
    email, exp = entry
    if exp < time.time():
        _EMAIL_CACHE.pop(user_id, None)
        return None
    return email


def _cache_put_email(user_id: str, email: str) -> None:
    if len(_EMAIL_CACHE) >= _EMAIL_CACHE_MAX_ENTRIES:
        oldest = min(_EMAIL_CACHE.items(), key=lambda kv: kv[1][1])[0]
        _EMAIL_CACHE.pop(oldest, None)
    _EMAIL_CACHE[user_id] = (email, time.time() + _EMAIL_CACHE_TTL_S)


async def _resolve_email(user_id: str, access_jwt: str) -> Optional[str]:
    cached = _cache_get_email(user_id)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient(
            base_url=_DIRECTUS_INTERNAL_URL, timeout=5.0
        ) as client:
            r = await client.get(
                "/users/me",
                params={"fields": "id,email"},
                headers={"Authorization": f"Bearer {access_jwt}"},
            )
        if r.status_code != 200:
            return None
        email = r.json().get("data", {}).get("email")
        if not email:
            return None
    except httpx.HTTPError:
        _logger.exception("forward_auth: /users/me call failed")
        return None
    _cache_put_email(user_id, email)
    return email


@router.get("/forward", include_in_schema=False)
async def forward_auth(
    response: Response,
    cookie: str | None = Header(default=None, alias="Cookie"),
) -> Response:
    """Validate the inbound request's Directus session and emit Remote-User."""
    if not cookie:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response

    token = _extract_session_token(cookie)
    if not token:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response

    try:
        # `iss=directus` is set by Directus on every session token. We don't
        # bind to `aud` because Directus doesn't set one; signature + exp +
        # iss check is sufficient.
        payload = jwt.decode(
            token,
            app_settings.DIRECTUS_SECRET,
            algorithms=["HS256"],
            issuer="directus",
        )
    except jwt.ExpiredSignatureError:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response
    except jwt.InvalidTokenError:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response

    user_id = payload.get("id")
    if not user_id:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return response

    email = await _resolve_email(user_id, token)
    if not email:
        # Token is valid but Directus rejected /users/me — fail closed.
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response

    response.headers["X-Remote-User"] = email
    response.status_code = status.HTTP_200_OK
    return response
