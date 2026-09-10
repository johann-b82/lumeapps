from uuid import UUID

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.security.roles import Role
from app.schemas import CurrentUser

_bearer = HTTPBearer(auto_error=False)  # D-07: we raise our own 401


def _role_map() -> dict[UUID, Role]:
    m = {
        settings.DIRECTUS_ADMINISTRATOR_ROLE_UUID: Role.ADMIN,
        settings.DIRECTUS_VIEWER_ROLE_UUID: Role.VIEWER,
    }
    # QS is an optional, interim module-scoped role (FAIR + ATR only). Only
    # active once a QS role UUID is provisioned in the environment.
    if settings.DIRECTUS_QS_ROLE_UUID is not None:
        m[settings.DIRECTUS_QS_ROLE_UUID] = Role.QS
    return m


_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="invalid or missing authentication token",
    headers={"WWW-Authenticate": "Bearer"},
)

# Kopfzeile, die die Oberfläche an jede Anfrage hängt (frontend/src/lib/
# apiClient.ts). Ein HTML-Formular auf einer fremden Seite kann sie nicht
# setzen, und ein fetch mit eigener Kopfzeile löst eine Vorabanfrage aus,
# die mangels CORS scheitert. Siehe _pruefe_csrf.
CSRF_KOPFZEILE = "x-lumeapps-request"

_SICHERE_METHODEN = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

_CSRF = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail=f"missing {CSRF_KOPFZEILE} header",
)


def _pruefe_csrf(request: Request | None) -> None:
    """Cookie-Anmeldung plus verändernde Methode? Dann Kopfzeile verlangen.

    Befund 9: die Sitzung steckt in einem Cookie, das der Browser bei jeder
    Anfrage an diesen Ursprung mitschickt — auch bei einer, die eine fremde
    Seite ausgelöst hat. ``SameSite=Lax`` fängt den geläufigen Fall ab, ist
    aber eine Einstellung, die Directus setzt, und kein Riegel, den wir
    selbst in der Hand haben. Diese Kopfzeile ist einer: sie lässt sich
    ursprungsübergreifend nicht setzen, ohne dass der Browser vorher
    nachfragt — und diese Nachfrage scheitert, weil hier kein CORS steht.

    Wer sich mit ``Authorization`` anmeldet (Dienste, Pi-Beiwagen, Tests),
    ist nicht betroffen: dieses Token schickt kein Browser von allein mit.
    """
    if request is None or request.method in _SICHERE_METHODEN:
        return
    if not request.headers.get(CSRF_KOPFZEILE):
        raise _CSRF


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    directus_session_token: str | None = Cookie(default=None),
) -> CurrentUser:
    # Token source priority: explicit Authorization header (legacy + service
    # callers) wins; otherwise fall back to the directus_session_token cookie
    # set by Directus 11 in session mode (frontend/src/lib/directusClient.ts
    # uses authentication("session", ...) so the SDK never returns an
    # access_token to the SPA — only the cookie is set).
    aus_kopfzeile = bool(credentials and credentials.credentials)
    token = credentials.credentials if aus_kopfzeile else directus_session_token
    if not token:
        raise _UNAUTHORIZED
    if not aus_kopfzeile:
        _pruefe_csrf(request)
    try:
        payload = jwt.decode(
            token,
            settings.DIRECTUS_SECRET,
            algorithms=["HS256"],
            # Directus 11 setzt `iss: "directus"` in jedem Token — geprüft
            # gegen 11.17.2, Login-Modus JSON wie Session. Ohne diese Prüfung
            # galt jedes mit DIRECTUS_SECRET signierte Token, egal wer es
            # ausgestellt hat.
            issuer="directus",
            # Ohne `require` akzeptierte pyjwt ein Token ganz ohne `exp`: es
            # wäre unbegrenzt gültig gewesen.
            options={"require": ["exp", "iat"]},
        )
    except jwt.PyJWTError:
        raise _UNAUTHORIZED

    # Directus stellt mit demselben Schlüssel auch Token für Freigabe-Links,
    # Einladungen und Passwort-Zurücksetzung aus. Die tragen keine `id`, würden
    # also unten ohnehin scheitern — hier scheitern sie mit klarer Absicht.
    if payload.get("share") is not None or payload.get("scope") is not None:
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


def _require_roles(*allowed: Role):
    """Factory for router-level role gates. Returns a dependency that admits
    only the listed roles; everything else gets 403. Assign the result to a
    module-global name so the router-gate audit tests can match it by identity.
    """
    allowed_set = frozenset(allowed)

    def dep(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="insufficient role",
            )
        return current_user

    return dep


# FAIR + ATR module gate: Admin (sees everything) plus the interim QS role.
require_atr_fair = _require_roles(Role.ADMIN, Role.QS)

# Dashboard-read gate: Admin plus Viewer. Excludes QS so the module-scoped QS
# role cannot read the viewer dashboards (KPI/HR/Quality/Finance/...).
require_dashboard_read = _require_roles(Role.ADMIN, Role.VIEWER)
