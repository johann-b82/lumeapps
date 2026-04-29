"""Phase 43 SGN-BE-06: tag-to-playlist resolver.

Per CONTEXT.md D-06/D-07/D-08/D-10:

  * D-06: Return an empty envelope (``playlist_id=None``, ``items=[]``) when
    the device has no tags or when no enabled playlist targets any of the
    device's tags. Uniform response shape for the kiosk loop.
  * D-07: On a successful match, items are ordered ``position ASC`` and carry
    ``media_id``, ``kind``, ``uri``, ``duration_ms``, ``transition``,
    ``position`` — pulled from the joined ``SignageMedia`` row.
  * D-08: Pick the best enabled playlist — ``priority DESC``, tie-broken by
    ``updated_at DESC`` — ``LIMIT 1``.
  * D-10: Pure read. The resolver does NOT update the device presence
    timestamp; that's ``/heartbeat``'s job.

Also hosts ``compute_playlist_etag`` (D-09) — the SHA256 helper the player
router will use for ``If-None-Match`` short-circuits in Plan 43-04.

Schema-side note: the ORM stores item duration as ``duration_s`` (seconds),
but the wire envelope exposes ``duration_ms`` per D-07. This module is the
single conversion point (``seconds * 1000``) so the wire format stays stable
even if we later migrate the column to milliseconds.
"""
from __future__ import annotations

import hashlib
import json
import uuid as _uuid
import zoneinfo
from datetime import datetime, timezone

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AppSettings
from app.models.signage import (
    SignageDevice,
    SignageDeviceTagMap,
    SignagePlaylist,
    SignagePlaylistItem,
    SignagePlaylistTagMap,
    SignageSchedule,
)
from app.schemas.signage import PlaylistEnvelope, PlaylistEnvelopeItem
from app.services._hhmm import now_hhmm_in_tz, time_to_hhmm


def _empty_envelope() -> PlaylistEnvelope:
    """Construct an empty envelope (D-06)."""
    return PlaylistEnvelope(
        playlist_id=None,
        name=None,
        items=[],
        resolved_at=datetime.now(timezone.utc),
    )


async def _build_envelope_for_playlist(
    db: AsyncSession, playlist_id: _uuid.UUID
) -> PlaylistEnvelope:
    """Load a playlist + its items/media and build the wire envelope.

    Used by both the tag-based branch of ``resolve_playlist_for_device`` and
    the new ``resolve_schedule_for_device`` so both paths return byte-identical
    envelopes (preserves D-08 etag invariant).
    """
    stmt = (
        select(SignagePlaylist)
        .where(SignagePlaylist.id == playlist_id)
        .options(
            selectinload(SignagePlaylist.items).selectinload(
                SignagePlaylistItem.media
            )
        )
    )
    playlist = (await db.execute(stmt)).scalar_one_or_none()
    if playlist is None:
        return _empty_envelope()

    # ORM relationship is already ordered by ``SignagePlaylistItem.position``
    # (see models.signage), but we sort again defensively — items come via
    # selectinload and a future relationship edit shouldn't silently break
    # envelope ordering.
    items_sorted = sorted(playlist.items, key=lambda it: it.position)
    envelope_items: list[PlaylistEnvelopeItem] = []
    for it in items_sorted:
        media = it.media
        envelope_items.append(
            PlaylistEnvelopeItem(
                media_id=it.media_id,
                kind=(media.kind if media is not None else ""),
                uri=(media.uri if (media is not None and media.uri) else ""),
                # duration_s → duration_ms (schema D-07 contract).
                duration_ms=int(it.duration_s) * 1000,
                transition=(it.transition or ""),
                position=it.position,
                # DEFECT-10: propagate html_content + slide_paths so the player
                # can render HTML and PPTX items.
                html=(media.html_content if media is not None else None),
                slide_paths=(media.slide_paths if media is not None else None),
            )
        )

    return PlaylistEnvelope(
        playlist_id=playlist.id,
        name=playlist.name,
        items=envelope_items,
        resolved_at=datetime.now(timezone.utc),
    )


async def resolve_schedule_for_device(
    db: AsyncSession,
    device: SignageDevice,
    *,
    now: datetime | None = None,
) -> PlaylistEnvelope | None:
    """Return best-matching schedule envelope, or ``None`` if no schedule matches.

    Phase 51 SGN-TIME-02. Pure-read (D-10). Tests override ``now=`` for
    determinism (Pitfall 5).

    Match algorithm:
      1. Load ``app_settings.timezone`` and compute ``(weekday, hhmm)`` once
         — all timezone handling is centralized in this call.
      2. Load device tag ids; if device has no tags, no schedule can match.
      3. Single SQL query joining ``signage_schedules → signage_playlists →
         signage_playlist_tag_map`` and filtering by weekday bit, time window
         (start_hhmm <= hhmm < end_hhmm), ``enabled=true``, and tag overlap.
         Order by ``priority DESC, updated_at DESC LIMIT 1``.
      4. If no row: return ``None``. Caller (``resolve_playlist_for_device``)
         falls back to the tag-based branch.
      5. Build an envelope via the shared ``_build_envelope_for_playlist``
         helper so schedule-matched and tag-matched envelopes are
         byte-identical (preserves ETag stability, D-08/D-09).
    """
    # 1. Load app-level timezone from the singleton settings row.
    settings = (
        await db.execute(select(AppSettings).where(AppSettings.id == 1))
    ).scalar_one()
    tz_name = settings.timezone

    # 2. Compute (weekday, hhmm) once.
    if now is None:
        weekday, hhmm = now_hhmm_in_tz(tz_name)
    else:
        # Convert provided `now` to the configured tz, then extract weekday+hhmm.
        now_in_tz = now.astimezone(zoneinfo.ZoneInfo(tz_name))
        weekday, hhmm = now_in_tz.weekday(), time_to_hhmm(now_in_tz.time())

    # 3. Device tag ids (reuse pattern from the tag-based branch).
    device_tag_rows = (
        await db.execute(
            select(SignageDeviceTagMap.tag_id).where(
                SignageDeviceTagMap.device_id == device.id
            )
        )
    ).scalars().all()
    if not device_tag_rows:
        return None
    device_tag_ids = list(device_tag_rows)

    # 4. Single SQL query. Bit-test is parameterized via bindparam — never
    #    interpolated into the SQL string (SQL-injection hygiene even though
    #    `weekday` is server-computed from zoneinfo).
    stmt = (
        select(SignageSchedule)
        .join(
            SignagePlaylist,
            SignagePlaylist.id == SignageSchedule.playlist_id,
        )
        .join(
            SignagePlaylistTagMap,
            SignagePlaylistTagMap.playlist_id == SignagePlaylist.id,
        )
        .where(
            SignageSchedule.enabled.is_(True),
            # Bit-test via parameterized SQL: (weekday_mask >> :weekday) & 1 = 1
            text(
                "(signage_schedules.weekday_mask >> :wd) & 1 = 1"
            ).bindparams(bindparam("wd", value=weekday)),
            SignageSchedule.start_hhmm <= hhmm,
            SignageSchedule.end_hhmm > hhmm,
            SignagePlaylistTagMap.tag_id.in_(device_tag_ids),
        )
        .order_by(
            SignageSchedule.priority.desc(),
            SignageSchedule.updated_at.desc(),
        )
        .limit(1)
    )
    result = (await db.execute(stmt)).scalar_one_or_none()
    if result is None:
        return None

    # 5. Shared envelope builder — identical shape to tag-resolved path.
    return await _build_envelope_for_playlist(db, result.playlist_id)


async def resolve_playlist_for_device(
    db: AsyncSession, device: SignageDevice
) -> PlaylistEnvelope:
    """Resolve the single best-matching playlist for a device.

    Phase 51 D-03 composition: time-aware schedule takes precedence. If
    ``resolve_schedule_for_device`` returns a non-empty envelope, that wins;
    otherwise fall through to the pre-Phase-51 tag-based branch (D-06/D-08).

    Returns the empty envelope when no tags / no match / match is disabled.
    Does NOT mutate the device row (D-10).

    Signature unchanged — all 8+ existing callsites continue to work.
    """
    # Phase 51 D-03: schedule-first composition.
    scheduled = await resolve_schedule_for_device(db, device)
    if scheduled is not None:
        return scheduled

    # --- Tag-based fallback (pre-Phase-51 behaviour) ---
    # Step 1: device tag ids.
    tag_rows = await db.execute(
        select(SignageDeviceTagMap.tag_id).where(
            SignageDeviceTagMap.device_id == device.id
        )
    )
    tag_ids = [row[0] for row in tag_rows.fetchall()]
    if not tag_ids:
        return _empty_envelope()

    # Step 2: best enabled matching playlist.
    playlist_stmt = (
        select(SignagePlaylist)
        .join(
            SignagePlaylistTagMap,
            SignagePlaylistTagMap.playlist_id == SignagePlaylist.id,
        )
        .where(
            SignagePlaylist.enabled.is_(True),
            SignagePlaylistTagMap.tag_id.in_(tag_ids),
        )
        .order_by(
            SignagePlaylist.priority.desc(),
            SignagePlaylist.updated_at.desc(),
        )
        .limit(1)
    )
    playlist = (await db.execute(playlist_stmt)).scalar_one_or_none()
    if playlist is None:
        return _empty_envelope()

    # Step 3: build envelope via shared helper.
    return await _build_envelope_for_playlist(db, playlist.id)


async def devices_affected_by_playlist(
    db: AsyncSession, playlist_id
) -> list:
    """Return device IDs whose resolved playlist could be affected by changes to the given playlist.

    A device is affected iff its tag set overlaps the playlist's target tag set
    (via signage_playlist_tag_map + signage_device_tag_map). Exact semantics mirror
    the reverse direction of resolve_playlist_for_device() — any device that could
    have this playlist chosen by the resolver is returned, regardless of priority
    (a higher-priority rival playlist may still win; the broadcast policy is "notify
    all candidates and let the player re-resolve via /playlist ETag").

    Revoked devices (``revoked_at IS NOT NULL``) are excluded — consistent with
    the other player paths; a revoked Pi has no valid SSE session anyway.

    Output sorted for deterministic test behavior.
    """
    stmt = (
        select(SignageDeviceTagMap.device_id)
        .join(
            SignagePlaylistTagMap,
            SignagePlaylistTagMap.tag_id == SignageDeviceTagMap.tag_id,
        )
        .join(
            SignageDevice,
            SignageDevice.id == SignageDeviceTagMap.device_id,
        )
        .where(
            SignagePlaylistTagMap.playlist_id == playlist_id,
            SignageDevice.revoked_at.is_(None),
        )
        .distinct()
    )
    rows = (await db.execute(stmt)).fetchall()
    return sorted({row[0] for row in rows})


async def devices_affected_by_device_update(
    db: AsyncSession, device_id
) -> list:
    """Return ``[device_id]`` — a device's own resolved playlist changes when its tags change.

    Trivial wrapper; exists so the admin ``devices.py`` notify hook
    (Plan 45-02) has a single consistent call shape across all mutation
    types (playlist-level vs. device-level changes).
    """
    return [device_id]


def compute_playlist_etag(envelope: PlaylistEnvelope) -> str:
    """SHA256 over a deterministic tuple (D-09). Used by Plan 43-04's router.

    Returns a stable hex-digest string so ``If-None-Match`` short-circuits
    only when ``(playlist_id, item positions/durations/transitions)`` is
    unchanged. The empty envelope has its own constant etag so every
    unmatched poll still validates.
    """
    if envelope.playlist_id is None:
        return hashlib.sha256(b"empty").hexdigest()
    parts: list[str] = [str(envelope.playlist_id)]
    for it in sorted(envelope.items, key=lambda i: i.position):
        parts.append(
            f"{it.media_id}:{it.position}:{it.duration_ms}:{it.transition}"
        )
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True).encode("utf-8")
    ).hexdigest()
