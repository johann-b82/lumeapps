"""Pydantic v2 schemas for the signage domain.

Mirrors the ORM models in `app.models.signage` on the DTO layer so FastAPI
routers in later phases (42, 43, 45, 46) can validate requests and serialize
responses without re-defining types.

Conventions (match existing `_base.py`):
- Every *Read schema ends with `model_config = {"from_attributes": True}`
- Literal types mirror DB CHECK constraints exactly
- Uses `uuid.UUID` and `datetime` directly
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------
# SignageMedia (D-06 / D-07 / D-08)
# --------------------------------------------------------------------------


class SignageMediaBase(BaseModel):
    kind: Literal["image", "video", "pdf", "pptx", "url", "html"]
    title: str = Field(..., max_length=255)
    mime_type: str | None = Field(default=None, max_length=127)
    size_bytes: int | None = None
    uri: str | None = None
    duration_ms: int | None = None
    html_content: str | None = None


class SignageMediaCreate(SignageMediaBase):
    pass


class SignageMediaRead(SignageMediaBase):
    id: uuid.UUID
    conversion_status: Literal["pending", "processing", "done", "failed"] | None = None
    slide_paths: list[str] | None = None
    conversion_error: str | None = None
    conversion_started_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------
# SignagePlaylist
# --------------------------------------------------------------------------


class SignagePlaylistBase(BaseModel):
    name: str = Field(..., max_length=128)
    description: str | None = None
    priority: int = 0
    enabled: bool = True
    # Populated by admin UI; resolved via signage_playlist_tag_map.
    tag_ids: list[int] | None = None


class SignagePlaylistRead(SignagePlaylistBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------
# SignagePlaylistItem
# --------------------------------------------------------------------------


class SignagePlaylistItemBase(BaseModel):
    media_id: uuid.UUID
    position: int
    duration_s: int = 10
    transition: str | None = Field(default=None, max_length=32)


class SignagePlaylistItemCreate(SignagePlaylistItemBase):
    pass


class SignagePlaylistItemRead(SignagePlaylistItemBase):
    id: uuid.UUID
    playlist_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------
# SignageDevice — admin may set name + tags; other fields read-only from API
# --------------------------------------------------------------------------


class SignageDeviceBase(BaseModel):
    """Parent of `SignageDeviceRead`. Retained because `SignageDeviceRead`
    inherits it; deletion would break the Phase 70 calibration PATCH
    response_model. (Phase 71-05 catch-all sweep — Plan flagged orphan but
    retained per Pitfall 7 inheritance guard.)
    """

    name: str = Field(..., max_length=128)
    tag_ids: list[int] | None = None


class SignageDeviceRead(SignageDeviceBase):
    id: uuid.UUID
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None
    current_item_id: uuid.UUID | None = None
    # Populated by admin list/get via the tag resolver (envelope.playlist_id/.name).
    # Null when no schedule/tag-mapped playlist matches the device's tags.
    current_playlist_id: uuid.UUID | None = None
    current_playlist_name: str | None = None
    status: Literal["online", "offline", "pending"]
    # Phase 62-01 CAL-BE-02 — calibration fields included in admin list/get.
    rotation: Literal[0, 90, 180, 270] = 0
    hdmi_mode: str | None = None
    audio_enabled: bool = False
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------
# Phase 62-01 Signage calibration — CAL-BE-03/05
# --------------------------------------------------------------------------


class SignageCalibrationRead(BaseModel):
    """Caller-scoped calibration — returned by GET /api/signage/player/calibration.

    Per CAL-BE-05 / D-10: the player-side shape is device-auth-scoped to the
    caller's own device. The sidecar fetches this on every ``calibration-changed``
    SSE event (D-04 / D-08 — event payload is device_id only, full state fetched
    here).
    """

    rotation: Literal[0, 90, 180, 270]
    hdmi_mode: str | None = None
    audio_enabled: bool
    model_config = ConfigDict(from_attributes=True)


class SignageCalibrationUpdate(BaseModel):
    """Admin PATCH body for /api/signage/devices/{id}/calibration — CAL-BE-03.

    All three fields optional (partial update). ``rotation`` typed as
    ``Literal[0, 90, 180, 270]`` so FastAPI/Pydantic rejects non-canonical
    values with HTTP 422 automatically (D-10 — no hand-rolled validation).
    """

    rotation: Literal[0, 90, 180, 270] | None = None
    hdmi_mode: str | None = Field(default=None, max_length=64)
    audio_enabled: bool | None = None


# --------------------------------------------------------------------------
# Pairing session schemas (used by Phase 42 pair router — defined here so
# Phase 42 does not re-declare). Decisions D-04 / D-05 will wire the
# alphabet in Phase 42; Phase 41 only defines schema width.
# --------------------------------------------------------------------------


class SignagePairingRequestResponse(BaseModel):
    # "XXX-XXX" display, 6 raw chars (7 incl. hyphen).
    pairing_code: str = Field(..., min_length=6, max_length=7)
    pairing_session_id: uuid.UUID
    expires_in: int  # seconds


class SignagePairingStatusResponse(BaseModel):
    status: Literal["pending", "claimed", "expired"]
    device_token: str | None = None  # set only on the first status poll after claim


class SignagePairingClaimRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=7)
    device_name: str = Field(..., max_length=128)
    tag_ids: list[int] | None = None


class SignagePairingSessionRead(BaseModel):
    id: uuid.UUID
    code: str
    device_id: uuid.UUID | None = None
    expires_at: datetime
    claimed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# -------------------- Phase 43: Player envelopes (D-06, D-07, D-11) --------------------


class PlaylistEnvelopeItem(BaseModel):
    """Single item in the resolved playlist envelope. D-07.

    Field mapping from ORM:
      - ``media_id``    <- ``SignagePlaylistItem.media_id``
      - ``kind``        <- ``SignageMedia.kind``
      - ``uri``         <- ``SignageMedia.uri`` (may be empty string if NULL)
      - ``duration_ms`` <- ``SignagePlaylistItem.duration_s * 1000``
      - ``transition``  <- ``SignagePlaylistItem.transition`` (empty string if NULL)
      - ``position``    <- ``SignagePlaylistItem.position``
    """
    model_config = ConfigDict(from_attributes=True)

    media_id: uuid.UUID
    kind: str
    uri: str
    duration_ms: int
    transition: str
    position: int
    # DEFECT-10: html and pptx items need payload fields on the envelope.
    # Frontend PlaybackShell already expects `html` and `slide_paths`; without
    # these, kind='html' renders nothing and kind='pptx' has no image sequence.
    html: str | None = None
    slide_paths: list[str] | None = None


class PlaylistEnvelope(BaseModel):
    """Tag-resolved playlist envelope returned by GET /api/signage/player/playlist.

    Empty when ``playlist_id`` is None and ``items`` is ``[]`` (D-06).
    """
    model_config = ConfigDict(from_attributes=True)

    playlist_id: uuid.UUID | None = None
    name: str | None = None
    items: list[PlaylistEnvelopeItem] = Field(default_factory=list)
    resolved_at: datetime


class DeviceAnalyticsRead(BaseModel):
    """Phase 53 SGN-ANA-01 — per-device analytics row.

    uptime_24h_pct is null ⇔ device has zero retained heartbeats (denominator 0);
    clients render a neutral '—' badge in that case (D-16).
    window_minutes is 0..1440 and drives the D-06 "over last Xh" tooltip.
    """
    model_config = ConfigDict(from_attributes=True)

    device_id: uuid.UUID
    uptime_24h_pct: float | None
    missed_windows_24h: int
    window_minutes: int


class HeartbeatRequest(BaseModel):
    """Player -> server heartbeat payload. D-11.

    Both fields are nullable so a just-booted player without a current item
    or cached ETag can still heartbeat.
    """
    model_config = ConfigDict(extra="ignore")

    current_item_id: uuid.UUID | None = None
    playlist_etag: str | None = None
