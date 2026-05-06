from uuid import UUID

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.security.roles import Role
from app.schemas import CurrentUser

_bearer = HTTPBearer(auto_error=False)  # D-07: we raise our own 401


def _role_map() -> dict[UUID, Role]:
    return {
        settings.DIRECTUS_ADMINISTRATOR_ROLE_UUID: Role.ADMIN,
        settings.DIRECTUS_VIEWER_ROLE_UUID: Role.VIEWER,
    }


_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="invalid or missing authentication token",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    directus_session_token: str | None = Cookie(default=None),
) -> CurrentUser:
    # Token source priority: explicit Authorization header (legacy + service
    # callers) wins; otherwise fall back to the directus_session_token cookie
    # set by Directus 11 in session mode (frontend/src/lib/directusClient.ts
    # uses authentication("session", ...) so the SDK never returns an
    # access_token to the SPA — only the cookie is set).
    token = credentials.credentials if credentials and credentials.credentials else directus_session_token
    if not token:
        raise _UNAUTHORIZED
    try:
        payload = jwt.decode(
            token,
            settings.DIRECTUS_SECRET,
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        raise _UNAUTHORIZED

    user_id_str = payload.get("id")
    role_uuid_str = payload.get("role")
    if not user_id_str or not role_uuid_str:
        raise _UNAUTHORIZED
    try:
        user_id = UUID(user_id_str)
        role_uuid = UUID(role_uuid_str)
    except (ValueError, TypeError):
        raise _UNAUTHORIZED

    role = _role_map().get(role_uuid)
    if role is None:
        raise _UNAUTHORIZED

    # Phase 27: email not in JWT — placeholder derived from id.
    # TODO(Phase 28+): fetch from Directus GET /users/{id}.
    return CurrentUser(
        id=user_id,
        email=f"{user_id}@directus.example.com",
        role=role,
    )


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin role required",
        )
    return current_user
