"""Unit tests for Phase 62-03 sidecar calibration extension.

Covers:
  Task 1: persistence helpers (_load_calibration / _save_calibration) + 0o600 mode
          heartbeat body extension with calibration_last_error / _last_applied_at
          _detect_audio_backend pin at startup
  Task 2: _apply_calibration argv shape (wlr-randr transform / mode; wpctl vs pactl)
          D-09 no-retry on subprocess failure
          D-06 boot replay ordering (before connectivity probe)
          Flag 1 — _wait_for_wayland_socket bounded poll
          SSE loop: calibration-changed → fetch + apply

All subprocess interaction is monkeypatched; no real wlr-randr / wpctl runs.
"""
from __future__ import annotations

import asyncio
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fresh-module fixture — same pattern as tests/test_sidecar.py::_fresh_sidecar
# ---------------------------------------------------------------------------

def _fresh_sidecar(tmp_path, monkeypatch):
    cache = tmp_path / "signage-cache"
    cache.mkdir(exist_ok=True)
    (cache / "media").mkdir(exist_ok=True)
    monkeypatch.setenv("SIGNAGE_CACHE_DIR", str(cache))
    monkeypatch.setenv("SIGNAGE_API_BASE", "http://upstream.test")
    for key in list(sys.modules.keys()):
        if key == "sidecar" or key.startswith("sidecar."):
            del sys.modules[key]
    sidecar_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if sidecar_dir not in sys.path:
        sys.path.insert(0, sidecar_dir)
    import sidecar as sc
    sc._device_token = None
    sc._online = False
    sc._playlist_body = None
    sc._playlist_etag = None
    sc._cached_media_ids = set()
    sc._calibration_last_error = None
    sc._calibration_last_applied_at = None
    sc._audio_backend = None
    sc._wlr_output_name = None
    return sc, cache


# ===========================================================================
# Task 1 — persistence + mode + heartbeat plumbing
# ===========================================================================

class TestCalibrationPersistence:
    def test_calibration_persistence_roundtrip(self, tmp_path, monkeypatch):
        """Write calibration dict, read it back, assert shape + 0o600 mode."""
        sc, cache = _fresh_sidecar(tmp_path, monkeypatch)
        payload = {"rotation": 90, "hdmi_mode": "1920x1080@60", "audio_enabled": True}
        sc._save_calibration(payload)
        # File persisted under SIGNAGE_CACHE_DIR/calibration.json at 0o600
        cal_path = cache / "calibration.json"
        assert cal_path.exists()
        mode = stat.S_IMODE(os.stat(cal_path).st_mode)
        assert mode == 0o600, f"expected 0600 got {oct(mode)}"
        # Round-trip equals original
        loaded = sc._load_calibration()
        assert loaded == payload

    def test_load_calibration_returns_none_when_absent(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        assert sc._load_calibration() is None

    def test_load_calibration_returns_none_on_corrupt_file(self, tmp_path, monkeypatch):
        sc, cache = _fresh_sidecar(tmp_path, monkeypatch)
        (cache / "calibration.json").write_text("{not-json")
        assert sc._load_calibration() is None


class TestAudioBackendDetect:
    def test_detect_audio_backend_prefers_wpctl(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        monkeypatch.setattr(sc.shutil, "which", lambda name: "/usr/bin/wpctl" if name == "wpctl" else "/usr/bin/pactl")
        assert sc._detect_audio_backend() == "wpctl"

    def test_detect_audio_backend_falls_back_to_pactl(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        monkeypatch.setattr(sc.shutil, "which", lambda name: "/usr/bin/pactl" if name == "pactl" else None)
        assert sc._detect_audio_backend() == "pactl"

    def test_detect_audio_backend_none_when_neither_available(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        monkeypatch.setattr(sc.shutil, "which", lambda name: None)
        assert sc._detect_audio_backend() is None


# ===========================================================================
# Task 2 — _apply_calibration argv shape + error handling
# ===========================================================================

class _FakeProc:
    """Minimal asyncio.subprocess.Process stub for argv-capture tests."""

    def __init__(self, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr

    async def wait(self):
        return self.returncode


def _make_exec_recorder(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
    """Return (fake_exec, calls_list). fake_exec records argv and returns _FakeProc."""
    calls: list[tuple] = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        return _FakeProc(returncode=returncode, stdout=stdout, stderr=stderr)

    return fake_exec, calls


_WLR_JSON_OUTPUT = json.dumps([
    {"name": "HDMI-A-1", "enabled": True, "modes": []},
    {"name": "HDMI-A-2", "enabled": False, "modes": []},
]).encode()


class TestApplyCalibration:
    def test_apply_calibration_rotation_invokes_wlr_randr_transform(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        fake_exec, calls = _make_exec_recorder(returncode=0, stdout=_WLR_JSON_OUTPUT)
        monkeypatch.setattr(sc.asyncio, "create_subprocess_exec", fake_exec)

        asyncio.run(sc._apply_calibration({"rotation": 90, "hdmi_mode": None, "audio_enabled": None}))

        # First call: wlr-randr --json (output discovery).  Second: transform.
        argvs = [list(c) for c in calls]
        assert ["wlr-randr", "--json"] in argvs
        assert any(a[:2] == ["wlr-randr", "--output"]
                   and "--transform" in a
                   and a[a.index("--transform") + 1] == "90"
                   for a in argvs)
        assert sc._calibration_last_error is None
        assert sc._calibration_last_applied_at is not None

    def test_apply_calibration_hdmi_mode_invokes_wlr_randr_mode(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        fake_exec, calls = _make_exec_recorder(returncode=0, stdout=_WLR_JSON_OUTPUT)
        monkeypatch.setattr(sc.asyncio, "create_subprocess_exec", fake_exec)

        asyncio.run(sc._apply_calibration({"rotation": None, "hdmi_mode": "1920x1080@60", "audio_enabled": None}))

        argvs = [list(c) for c in calls]
        assert any("--mode" in a and a[a.index("--mode") + 1] == "1920x1080@60" for a in argvs)

    def test_apply_calibration_audio_wpctl_preferred(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        sc._audio_backend = "wpctl"
        fake_exec, calls = _make_exec_recorder(returncode=0, stdout=_WLR_JSON_OUTPUT)
        monkeypatch.setattr(sc.asyncio, "create_subprocess_exec", fake_exec)

        asyncio.run(sc._apply_calibration({"rotation": None, "hdmi_mode": None, "audio_enabled": True}))

        argvs = [list(c) for c in calls]
        # audio_enabled=True → mute=0
        assert ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"] in argvs

    def test_apply_calibration_audio_pactl_fallback(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        sc._audio_backend = "pactl"
        fake_exec, calls = _make_exec_recorder(returncode=0, stdout=_WLR_JSON_OUTPUT)
        monkeypatch.setattr(sc.asyncio, "create_subprocess_exec", fake_exec)

        asyncio.run(sc._apply_calibration({"rotation": None, "hdmi_mode": None, "audio_enabled": False}))

        argvs = [list(c) for c in calls]
        assert ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"] in argvs

    def test_apply_calibration_subprocess_failure_records_error_no_retry(self, tmp_path, monkeypatch):
        """D-09: on subprocess failure, record error; do NOT retry internally."""
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        call_count = {"n": 0}

        async def fake_exec(*args, **kwargs):
            call_count["n"] += 1
            # wlr-randr --json succeeds; everything else fails
            if args[:2] == ("wlr-randr", "--json"):
                return _FakeProc(returncode=0, stdout=_WLR_JSON_OUTPUT)
            return _FakeProc(returncode=2, stderr=b"invalid mode")

        monkeypatch.setattr(sc.asyncio, "create_subprocess_exec", fake_exec)

        asyncio.run(sc._apply_calibration({"rotation": 90, "hdmi_mode": None, "audio_enabled": None}))

        assert sc._calibration_last_error is not None
        assert "invalid mode" in sc._calibration_last_error or "2" in sc._calibration_last_error
        # Exactly 2 exec calls: one discovery, one transform. No retry.
        assert call_count["n"] == 2

    def test_apply_calibration_persists_on_success(self, tmp_path, monkeypatch):
        sc, cache = _fresh_sidecar(tmp_path, monkeypatch)
        fake_exec, _ = _make_exec_recorder(returncode=0, stdout=_WLR_JSON_OUTPUT)
        monkeypatch.setattr(sc.asyncio, "create_subprocess_exec", fake_exec)
        payload = {"rotation": 180, "hdmi_mode": None, "audio_enabled": None}
        asyncio.run(sc._apply_calibration(payload))
        loaded = sc._load_calibration()
        assert loaded == payload


# ===========================================================================
# Flag 1 — _wait_for_wayland_socket bounded poll
# ===========================================================================

class TestWaylandSocketWait:
    def test_wait_for_wayland_socket_returns_true_when_present(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir()
        (runtime_dir / "wayland-0").write_text("")  # socket placeholder
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))
        result = asyncio.run(sc._wait_for_wayland_socket(timeout=1.0))
        assert result is True

    def test_wait_for_wayland_socket_returns_false_on_timeout(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        runtime_dir = tmp_path / "nonexistent-runtime"
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))
        result = asyncio.run(sc._wait_for_wayland_socket(timeout=0.3))
        assert result is False
        assert sc._calibration_last_error is not None
        assert "wayland" in sc._calibration_last_error.lower()

    def test_replay_skipped_when_wayland_unavailable(self, tmp_path, monkeypatch):
        """If _wait_for_wayland_socket returns False, _replay_persisted_calibration
        must not call _apply_calibration."""
        sc, cache = _fresh_sidecar(tmp_path, monkeypatch)
        # Persist a calibration so there's something to replay
        sc._save_calibration({"rotation": 90, "hdmi_mode": None, "audio_enabled": None})

        apply_calls = []

        async def fake_apply(cal):
            apply_calls.append(cal)

        monkeypatch.setattr(sc, "_apply_calibration", fake_apply)

        async def scenario():
            ready = await sc._wait_for_wayland_socket(timeout=0.2)
            if ready:
                await sc._replay_persisted_calibration()

        # Point XDG_RUNTIME_DIR at a non-existent path so wait returns False
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "absent"))
        asyncio.run(scenario())
        assert apply_calls == []


# ===========================================================================
# D-06 — replay on boot runs before connectivity probe
# ===========================================================================

class TestBootReplayOrdering:
    def test_replay_on_boot_runs_before_connectivity_probe(self, tmp_path, monkeypatch):
        """Verify that during lifespan startup, _replay_persisted_calibration
        completes BEFORE the connectivity probe loop can make its first HTTP call."""
        sc, cache = _fresh_sidecar(tmp_path, monkeypatch)
        # Persist a calibration + token so both paths have work
        sc._save_calibration({"rotation": 90, "hdmi_mode": None, "audio_enabled": None})

        ordering: list[str] = []

        async def fake_wait(timeout=15.0):
            return True

        async def fake_apply(cal):
            ordering.append("apply_calibration")

        original_probe = sc._connectivity_probe_loop

        async def fake_probe():
            ordering.append("probe_started")
            # Don't actually loop; return immediately
            return

        async def fake_refresh():
            return

        async def fake_heartbeat():
            return

        async def fake_sse():
            return

        monkeypatch.setattr(sc, "_wait_for_wayland_socket", fake_wait)
        monkeypatch.setattr(sc, "_apply_calibration", fake_apply)
        monkeypatch.setattr(sc, "_connectivity_probe_loop", fake_probe)
        monkeypatch.setattr(sc, "_playlist_refresh_loop", fake_refresh)
        monkeypatch.setattr(sc, "_heartbeat_loop", fake_heartbeat)
        monkeypatch.setattr(sc, "_calibration_sse_loop", fake_sse)

        async def drive():
            async with sc.lifespan(sc.app):
                # Give spawned tasks a tick to run
                await asyncio.sleep(0.05)

        asyncio.run(drive())

        # apply_calibration must appear and must be first
        assert "apply_calibration" in ordering
        assert ordering.index("apply_calibration") < ordering.index("probe_started")


# ===========================================================================
# Task 2 — SSE loop
# ===========================================================================

class TestSseCalibrationLoop:
    def test_sse_loop_calibration_changed_triggers_fetch_and_apply(self, tmp_path, monkeypatch):
        """On calibration-changed event, loop fetches /player/calibration and
        calls _apply_calibration with the response payload."""
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        sc._device_token = "dev.jwt.token"
        sc._online = True

        applied: list[dict] = []

        async def fake_apply(cal):
            applied.append(cal)

        monkeypatch.setattr(sc, "_apply_calibration", fake_apply)

        # Mock aconnect_sse to yield a single event, then raise to exit the loop
        class _Event:
            def __init__(self, data: str):
                self.data = data

            def json(self):
                return json.loads(self.data)

        class _SseCtx:
            def __init__(self, events):
                self._events = events

            async def __aenter__(self):
                outer = self

                class _SseConn:
                    async def aiter_sse(self_inner):
                        for e in outer._events:
                            yield e
                        # After yielding, force loop to break out via cancelled
                        raise asyncio.CancelledError()

                return _SseConn()

            async def __aexit__(self, *args):
                return False

        def fake_aconnect_sse(client, method, url, **kwargs):
            return _SseCtx([_Event(json.dumps({"event": "calibration-changed", "device_id": "abc"}))])

        monkeypatch.setattr(sc, "aconnect_sse", fake_aconnect_sse)

        # Mock the GET /calibration fetch
        calibration_payload = {"rotation": 270, "hdmi_mode": "1280x720@60", "audio_enabled": True}

        class _FakeResponse:
            status_code = 200

            def json(self):
                return calibration_payload

        class _FakeClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, headers=None, timeout=None):
                return _FakeResponse()

        monkeypatch.setattr(sc.httpx, "AsyncClient", _FakeClient)

        async def drive():
            try:
                await asyncio.wait_for(sc._calibration_sse_loop(), timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        asyncio.run(drive())
        assert applied == [calibration_payload]
