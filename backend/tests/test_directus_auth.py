from uuid import UUID

import pytest
from fastapi import FastAPI, Depends
from httpx import AsyncClient, ASGITransport

from app.security.directus_auth import get_current_user
from app.security.roles import Role
from app.schemas import CurrentUser

# Back-compat re-exports — many tests import these symbols from this module.
# Canonical home is `tests/_auth.py` since v1.24 A-1.
from tests._auth import (  # noqa: F401
    DIRECTUS_SECRET,
    ADMIN_UUID,
    VIEWER_UUID,
    USER_UUID,
    mint as _mint,
)


@pytest.fixture
def app():
    a = FastAPI()

    @a.get("/protected")
    async def protected(user: CurrentUser = Depends(get_current_user)):
        return {"id": str(user.id), "email": user.email, "role": user.role.value}

    @a.get("/health")
    async def health():
        return {"status": "ok"}

    return a


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_valid_admin_token_resolves_admin(client):
    token = _mint(ADMIN_UUID)
    r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["role"] == Role.ADMIN.value


async def test_valid_viewer_token_resolves_viewer(client):
    token = _mint(VIEWER_UUID)
    r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["role"] == Role.VIEWER.value


async def test_expired_token_returns_401(client):
    token = _mint(ADMIN_UUID, exp_minutes=-5)
    r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid or missing authentication token"


async def test_wrong_signature_returns_401(client):
    token = _mint(ADMIN_UUID, secret="a-completely-different-secret")
    r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid or missing authentication token"


async def test_malformed_bearer_returns_401(client):
    r = await client.get("/protected", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid or missing authentication token"


async def test_missing_authorization_returns_401(client):
    r = await client.get("/protected")
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid or missing authentication token"


async def test_unknown_role_uuid_returns_401(client):
    token = _mint("99999999-9999-9999-9999-999999999999")
    r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid or missing authentication token"


async def test_health_endpoint_no_auth_needed(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# --- End-to-end against real app (Plan 27-02) ---

async def test_real_api_route_requires_bearer():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/kpis")
        assert r.status_code == 401
        assert r.json()["detail"] == "invalid or missing authentication token"


async def test_real_api_route_accepts_valid_bearer():
    from app.main import app
    token = _mint(VIEWER_UUID)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/kpis", headers={"Authorization": f"Bearer {token}"})
        # Must not be 401 — auth passed. May be 200, 404, 422, or 5xx depending on DB state;
        # the only failure we're asserting against is auth rejection.
        assert r.status_code != 401, f"Expected auth to pass, got 401: {r.json()}"


async def test_real_health_endpoint_no_auth():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/health")
        assert r.status_code == 200


# --- Token-Herkunft und Ablauf (Befund 3) ---
#
# Die Prüfung akzeptierte jedes mit DIRECTUS_SECRET signierte Token, das eine
# bekannte Rollen-UUID trug: ohne Ausstellerprüfung und ohne Pflicht-`exp`.
# Die Payload-Form unten ist gegen Directus 11.17.2 abgeglichen (Login-Modus
# JSON und Session; beide tragen id, role, iat, exp, iss="directus").

async def test_fremder_aussteller_wird_abgelehnt(client):
    token = _mint(ADMIN_UUID, extra={"iss": "jemand-anderes"})
    r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_token_ohne_aussteller_wird_abgelehnt(client):
    import jwt as _jwt
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    token = _jwt.encode(
        {
            "id": USER_UUID,
            "role": ADMIN_UUID,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
        },
        DIRECTUS_SECRET,
        algorithm="HS256",
    )
    r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_token_ohne_ablauf_wird_abgelehnt(client):
    """Vorher unbegrenzt gültig."""
    import jwt as _jwt
    from datetime import datetime, timezone

    token = _jwt.encode(
        {
            "id": USER_UUID,
            "role": ADMIN_UUID,
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "iss": "directus",
        },
        DIRECTUS_SECRET,
        algorithm="HS256",
    )
    r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_freigabe_token_wird_abgelehnt(client):
    """Directus signiert Freigabe-Links mit demselben Schlüssel."""
    token = _mint(ADMIN_UUID, extra={"share": "a1b2c3", "share_scope": {}})
    r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_zurueckgesetztes_passwort_token_wird_abgelehnt(client):
    token = _mint(ADMIN_UUID, extra={"scope": "password-reset"})
    r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_echtes_directus_token_geht_weiterhin_durch(client):
    """Form wie von Directus 11.17.2 ausgestellt, Session-Modus."""
    token = _mint(ADMIN_UUID, extra={"app_access": True, "admin_access": True, "session": "abc"})
    r = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
