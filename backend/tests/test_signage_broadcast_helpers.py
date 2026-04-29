"""Unit tests for signage_broadcast high-level notify_* helpers (Phase A)."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.services import signage_broadcast


@pytest.mark.asyncio
async def test_notify_playlist_changed_emits_per_affected_device(monkeypatch):
    pid = uuid.uuid4()
    dev_a, dev_b = 11, 22
    sent: list[tuple[int, dict]] = []

    async def fake_affected(db, playlist_id):
        assert playlist_id == pid
        return [dev_a, dev_b]

    async def fake_resolve(db, dev):
        return {"slides": [], "device_id": dev.id}

    def fake_etag(env):
        return f"etag-{env['device_id']}"

    monkeypatch.setattr(signage_broadcast, "devices_affected_by_playlist", fake_affected, raising=False)
    monkeypatch.setattr(signage_broadcast, "resolve_playlist_for_device", fake_resolve, raising=False)
    monkeypatch.setattr(signage_broadcast, "compute_playlist_etag", fake_etag, raising=False)

    class _Dev:
        def __init__(self, _id): self.id = _id

    async def fake_load(db, device_id):
        return _Dev(device_id)

    monkeypatch.setattr(signage_broadcast, "_load_device", fake_load, raising=False)

    with patch.object(signage_broadcast, "notify_device", side_effect=lambda d, p: sent.append((d, p))):
        await signage_broadcast.notify_playlist_changed(db=None, playlist_id=pid)

    assert [d for d, _ in sent] == [dev_a, dev_b]
    assert all(p["event"] == "playlist-changed" for _, p in sent)
    assert all(p["playlist_id"] == str(pid) for _, p in sent)
    assert sent[0][1]["etag"] == "etag-11"


@pytest.mark.asyncio
async def test_notify_playlist_changed_delete_uses_literal_etag(monkeypatch):
    pid = uuid.uuid4()
    sent: list[tuple[int, dict]] = []
    with patch.object(signage_broadcast, "notify_device", side_effect=lambda d, p: sent.append((d, p))):
        await signage_broadcast.notify_playlist_changed(
            db=None, playlist_id=pid, affected=[1, 2, 3], deleted=True
        )
    assert [d for d, _ in sent] == [1, 2, 3]
    assert {p["etag"] for _, p in sent} == {"deleted"}
    assert {p["playlist_id"] for _, p in sent} == {str(pid)}


@pytest.mark.asyncio
async def test_notify_devices_for_media_dispatches_per_referenced_playlist(monkeypatch):
    media_id = uuid.uuid4()
    playlist_ids = [uuid.uuid4(), uuid.uuid4()]
    calls: list = []

    async def fake_referenced(db, mid):
        assert mid == media_id
        return playlist_ids

    async def fake_notify_playlist(db, playlist_id, **kw):
        calls.append(playlist_id)

    monkeypatch.setattr(signage_broadcast, "_playlists_referencing_media", fake_referenced, raising=False)
    monkeypatch.setattr(signage_broadcast, "notify_playlist_changed", fake_notify_playlist)

    await signage_broadcast.notify_devices_for_media(db=None, media_id=media_id)

    assert calls == playlist_ids


@pytest.mark.asyncio
async def test_notify_device_self_emits_resolved_envelope_etag(monkeypatch):
    dev_id = 99
    sent: list[tuple[int, dict]] = []

    class _Dev:
        def __init__(self, _id): self.id = _id

    async def fake_load(db, device_id):
        return _Dev(device_id)

    async def fake_resolve(db, dev):
        return {"device_id": dev.id, "slides": []}

    def fake_etag(env):
        return "etag-self"

    monkeypatch.setattr(signage_broadcast, "_load_device", fake_load, raising=False)
    monkeypatch.setattr(signage_broadcast, "resolve_playlist_for_device", fake_resolve, raising=False)
    monkeypatch.setattr(signage_broadcast, "compute_playlist_etag", fake_etag, raising=False)

    with patch.object(signage_broadcast, "notify_device", side_effect=lambda d, p: sent.append((d, p))):
        await signage_broadcast.notify_device_self(db=None, device_id=dev_id)

    assert sent == [(dev_id, {"event": "playlist-changed", "device_id": str(dev_id), "etag": "etag-self"})]
