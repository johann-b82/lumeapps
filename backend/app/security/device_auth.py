"""Device JWT authentication dependency — SGN-BE-04.

Mirrors `app.security.directus_auth.get_current_user` conventions:
    - HTTPBearer(auto_error=False) + explicit 401 raise with WWW-Authenticate
    - Explicit `algorithms=["HS256"]` on jwt.decode (alg-confusion defense)
    - Catch base `jwt.PyJWTError` → 401 (never 400)

Semantics (D-14):
    - A signed token with `scope != "device"` → 401 (wrong audience)
    - A valid token whose device row has `revoked_at IS NOT NULL` → 401
      (treat as "token no longer valid for us", not 403)
    - Missing / malformed / expired / bad-signature token → 401
"""
from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_db_session
from app.models import SignageDevice

_bearer = HTTPBearer(auto_error=False)  # convention: explicit raise, not 403 auto

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="invalid or missing device token",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_device(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_async_db_session),
) -> SignageDevice:
    """Resolve `Authorization: Bearer <jwt>` → SignageDevice row or 401.

    Phase 47 OQ4: fall back to ``?token=<jwt>`` query param when the
    ``Authorization`` header is absent. Browsers cannot set custom headers on
    ``EventSource``, and Phase 42 already chose query-string SSE auth at the
    system level (Phase 45 D-01 / Phase 47 RESEARCH Pitfall P7); this is the
    wiring catch-up so the device player can subscribe to
    ``/api/signage/player/stream?token=…``.
    """
    token = (
        credentials.credentials
        if credentials is not None and credentials.credentials
        else request.query_params.get("token")
    )
    if not token:
        raise _UNAUTHORIZED

    try:
        payload = jwt.decode(
            token,
            settings.SIGNAGE_DEVICE_JWT_SECRET,
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        raise _UNAUTHORIZED

    # Scope enforcement (D-01): tokens minted for other audiences must not pass.
    if payload.get("scope") != "device":
        raise _UNAUTHORIZED

    sub = payload.get("sub")
    try:
        device_id = UUID(sub) if sub is not None else None
    except (ValueError, TypeError):
        raise _UNAUTHORIZED
    if device_id is None:
        raise _UNAUTHORIZED

    result = await db.execute(
        select(SignageDevice).where(SignageDevice.id == device_id)
    )
    device = result.scalar_one_or_none()
    if device is None or device.revoked_at is not None:
        # D-14: revoked → 401, never 403. The token's signature is valid, but
        # we treat it as no-longer-valid for this server.
        raise _UNAUTHORIZED
    return device
