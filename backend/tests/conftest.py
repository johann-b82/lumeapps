"""Async test harness for backend/tests/.

Provides:
  - `client`: httpx.AsyncClient bound to the FastAPI ASGI app via ASGITransport,
    wrapped in asgi-lifespan's LifespanManager so startup/shutdown events fire.
  - `reset_settings`: autouse fixture that resets the app_settings singleton row
    to DEFAULT_SETTINGS before each test, guaranteeing isolation.
"""
import os

os.environ.setdefault("DIRECTUS_SECRET", "test-directus-secret-phase-27")
os.environ.setdefault("DIRECTUS_ADMINISTRATOR_ROLE_UUID", "c1111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
os.environ.setdefault("DIRECTUS_VIEWER_ROLE_UUID", "a2222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
os.environ.setdefault("SIGNAGE_DEVICE_JWT_SECRET", "test-signage-device-jwt-secret-phase-42")
# Defaults required for app.database module import during test collection
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("POSTGRES_HOST", "localhost")
# In-container default for Directus integration tests; host runs override via .env.
os.environ.setdefault("DIRECTUS_BASE_URL", "http://directus:8055")

import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client():
    # Dispose the shared async engine's pool so this test's event loop gets
    # fresh connections. Without this, asyncpg raises "another operation is in
    # progress" / "attached to a different loop" when the module-level engine
    # (created during earlier tests with different loops) is reused.
    from app.database import engine

    await engine.dispose()
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    await engine.dispose()


@pytest_asyncio.fixture
async def admin_client(client):
    """`client` pre-authenticated as an Admin via a freshly-minted Directus JWT.

    Use for tests that need to hit admin-gated routes. v1.24 A-1.
    """
    from tests._auth import ADMIN_UUID, mint

    client.headers["Authorization"] = f"Bearer {mint(ADMIN_UUID)}"
    yield client


@pytest_asyncio.fixture
async def viewer_client(client):
    """`client` pre-authenticated as a Viewer."""
    from tests._auth import VIEWER_UUID, mint

    client.headers["Authorization"] = f"Bearer {mint(VIEWER_UUID)}"
    yield client


@pytest_asyncio.fixture(autouse=True)
async def reset_settings():
    """Reset app_settings singleton to DEFAULT_SETTINGS before each test.

    Guarded by ImportError because AppSettings / DEFAULT_SETTINGS are created in
    Plans 02 and 03 of this phase; before those merge, this fixture is a no-op
    so `pytest --collect-only` still works on a partial tree.
    """
    try:
        from sqlalchemy import update
        from sqlalchemy.exc import SQLAlchemyError

        from app.database import AsyncSessionLocal, engine
        from app.defaults import DEFAULT_SETTINGS
        from app.models import AppSettings
    except ImportError:
        yield
        return

    # Dispose the pool so this event loop gets fresh connections — avoids
    # asyncpg "another operation is in progress" when module-level engine
    # is reused across tests with different loops.
    try:
        await engine.dispose()
    except Exception:
        pass

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(AppSettings)
                .where(AppSettings.id == 1)
                .values(
                    logo_data=None,
                    logo_mime=None,
                    logo_updated_at=None,
                    **DEFAULT_SETTINGS,
                )
            )
            await db.commit()
    except (SQLAlchemyError, RuntimeError, OSError):
        # Table may not exist yet in a partial Wave 2 tree (Plans 04-02/04-03
        # create `app_settings`). Pure unit tests that don't need DB isolation
        # should still run — let them proceed as a no-op. RuntimeError catches
        # the "attached to a different loop" fragility when the module-scoped
        # async engine outlives a parametrized test's event loop. OSError catches
        # socket/DNS errors when no database is reachable (e.g. auth unit tests).
        pass
    yield
