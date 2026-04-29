"""Phase 43 SGN-BE-01: admin CRUD router package.

Per CONTEXT D-01: one router-level admin gate. `require_admin` MUST appear
exactly once here. Sub-routers MUST NOT add their own `require_admin` or
`get_current_user` dependencies.
"""
from fastapi import APIRouter, Depends

from app.security.directus_auth import get_current_user, require_admin

from . import analytics, devices, media, playlist_items, playlists, resolved

router = APIRouter(
    prefix="/api/signage",
    tags=["signage-admin"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)
router.include_router(analytics.router)
router.include_router(media.router)
router.include_router(playlists.router)
router.include_router(playlist_items.router)
router.include_router(devices.router)
router.include_router(resolved.router)
