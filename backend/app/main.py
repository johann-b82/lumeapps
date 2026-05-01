from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database import engine
from app.routers.kpis import router as kpis_router
from app.routers.sensors import router as sensors_router
from app.routers.settings import router as settings_router, public_router as settings_public_router
from app.routers.sync import router as sync_router
from app.routers.uploads import admin_router as uploads_admin_router
from app.routers.hr_kpis import router as hr_kpis_router
from app.routers.hr_overtime import router as hr_overtime_router
from app.routers.signage_pair import router as signage_pair_router
from app.routers.signage_player import router as signage_player_router
from app.routers.signage_admin import router as signage_admin_router
from app.routers.sales_aliases import router as sales_aliases_router
from app.scheduler import lifespan

app = FastAPI(title="KPI Dashboard", lifespan=lifespan)

app.include_router(uploads_admin_router)
app.include_router(kpis_router)
app.include_router(settings_router)
app.include_router(settings_public_router)
app.include_router(sync_router)
app.include_router(sensors_router)
app.include_router(hr_kpis_router)
app.include_router(hr_overtime_router)
app.include_router(signage_pair_router)
app.include_router(signage_player_router)
app.include_router(signage_admin_router)
app.include_router(sales_aliases_router)


# ---------------------------------------------------------------------------
# Phase 47: Player bundle static-file serving.
# Mount AFTER all /api/* routers so the catch-all never shadows API routes.
# Mount only when the bundle has been built (guard makes pytest a no-op).
#
# Pitfall P6 (RESEARCH): The SPA-fallback route MUST check whether the
# requested path resolves to a real file in dist/player/ FIRST and serve it
# directly with the right Content-Type. Otherwise GET /player/sw.js returns
# text/html, the browser refuses to register the SW, and the PWA breaks.
# ---------------------------------------------------------------------------

# DEFECT-6: in the container, /app is the backend root (not the repo root), so
# parents[2] resolves to "/" and PLAYER_DIST ends up at /frontend/dist/player
# — breaking the player mount. Allow an env override, and default to a path
# that works both on-host (repo-root/frontend/dist/player) and in-container
# when docker-compose bind-mounts ./frontend/dist to /app/frontend/dist.
import os as _os

_env_override = _os.environ.get("SIGNAGE_PLAYER_DIST")
if _env_override:
    PLAYER_DIST = Path(_env_override)
else:
    _backend_root = Path(__file__).resolve().parents[1]  # /app  (container) or repo/backend (host)
    _in_container = _backend_root / "frontend" / "dist" / "player"
    _on_host = Path(__file__).resolve().parents[2] / "frontend" / "dist" / "player"
    PLAYER_DIST = _in_container if _in_container.exists() else _on_host

if PLAYER_DIST.exists():
    # /player/assets/* → static files (hashed JS/CSS chunks). StaticFiles serves
    # with correct MIME types based on file extension.
    app.mount(
        "/player/assets",
        StaticFiles(directory=PLAYER_DIST / "assets"),
        name="player-assets",
    )

    # SPA fallback for everything under /player/. ORDER MATTERS:
    # 1. If path is empty (/player/ or /player) → serve index.html
    # 2. Else if path resolves to a real file in dist/player/ root → serve it
    #    (covers /player/sw.js, /player/manifest.webmanifest, /player/icon-192.png,
    #    /player/registerSW.js)
    # 3. Else → serve index.html (wouter parses /:token client-side)
    @app.get("/player")
    @app.get("/player/")
    @app.get("/player/{path:path}")
    async def _player_spa_fallback(path: str = "") -> FileResponse:
        if path:
            # Defend against path traversal: resolve and confirm parent IS PLAYER_DIST.
            candidate = (PLAYER_DIST / path).resolve()
            if (
                candidate.is_file()
                and PLAYER_DIST.resolve() in candidate.parents
                and candidate.parent == PLAYER_DIST.resolve()
            ):
                return FileResponse(candidate)
        return FileResponse(PLAYER_DIST / "index.html")


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"DB unavailable: {exc}") from exc
