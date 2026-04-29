"""Schemas package — re-exports every Pydantic v2 class.

Keeps ``from app.schemas import X`` stable for all existing callers
(legacy classes live in ``_base.py``; signage classes live in ``signage.py``).
"""
from app.schemas._base import *  # noqa: F401,F403 — re-export legacy classes
from app.schemas.signage import (  # noqa: F401
    SignageDeviceBase,
    SignageDeviceRead,
    SignageMediaBase,
    SignageMediaCreate,
    SignageMediaRead,
    SignagePairingClaimRequest,
    SignagePairingRequestResponse,
    SignagePairingSessionRead,
    SignagePairingStatusResponse,
    SignagePlaylistBase,
    SignagePlaylistItemBase,
    SignagePlaylistItemCreate,
    SignagePlaylistItemRead,
    SignagePlaylistRead,
)
