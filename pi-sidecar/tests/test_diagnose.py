"""Unit tests for the --diagnose mode (Phase 74 / PI-01).

Mirrors the test_calibration.py harness: sys.modules reload + _FakeProc
argv-recorder + httpx-sse mock. All I/O is mocked; no real Pi or backend needed.
"""
from __future__ import annotations

import asyncio
import json
import os
import stat
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fresh-module fixture — same pattern as test_calibration.py::_fresh_sidecar
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


_WLR_JSON_OUTPUT = json.dumps([
    {"name": "HDMI-A-1", "enabled": True, "modes": []}
]).encode()


def _write_token(cache: Path, content: str = "fake-jwt", mode: int = 0o600) -> Path:
    p = cache / "device_token"
    p.write_text(content)
    os.chmod(p, mode)
    return p


# ---------------------------------------------------------------------------
# probe_01_api_base
# ---------------------------------------------------------------------------

class TestProbe01:
    def test_pass(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        monkeypatch.setenv("SIGNAGE_API_BASE", "http://lan.test:8000")
        r = asyncio.run(sc.probe_01_api_base())
        assert r.status == "PASS"
        assert r.observed == "http://lan.test:8000"

    def test_fail_empty(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        monkeypatch.setenv("SIGNAGE_API_BASE", "")
        r = asyncio.run(sc.probe_01_api_base())
        assert r.status == "FAIL"
        assert "<empty>" in r.observed

    def test_fail_placeholder_leak(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        monkeypatch.setenv("SIGNAGE_API_BASE", "http://__SIGNAGE_API_URL__:8000")
        r = asyncio.run(sc.probe_01_api_base())
        assert r.status == "FAIL"
        assert "__SIGNAGE_" in r.observed


# ---------------------------------------------------------------------------
# probe_02_device_token
# ---------------------------------------------------------------------------

class TestProbe02:
    def test_pass(self, tmp_path, monkeypatch):
        sc, cache = _fresh_sidecar(tmp_path, monkeypatch)
        _write_token(cache, "abc.def.ghi", 0o600)
        r = asyncio.run(sc.probe_02_device_token())
        assert r.status == "PASS", r.raw

    def test_fail_absent(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        r = asyncio.run(sc.probe_02_device_token())
        assert r.status == "FAIL"
        assert "absent" in r.observed

    def test_fail_wrong_mode(self, tmp_path, monkeypatch):
        sc, cache = _fresh_sidecar(tmp_path, monkeypatch)
        _write_token(cache, "abc", 0o644)
        r = asyncio.run(sc.probe_02_device_token())
        assert r.status == "FAIL"

    def test_fail_empty(self, tmp_path, monkeypatch):
        sc, cache = _fresh_sidecar(tmp_path, monkeypatch)
        _write_token(cache, "", 0o600)
        r = asyncio.run(sc.probe_02_device_token())
        assert r.status == "FAIL"


# ---------------------------------------------------------------------------
# probe_03_wayland_env
# ---------------------------------------------------------------------------

class TestProbe03:
    def test_pass(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        xdg = tmp_path / "run-user"
        xdg.mkdir()
        (xdg / "wayland-0").touch()
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(xdg))
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        r = asyncio.run(sc.probe_03_wayland_env())
        assert r.status == "PASS", r.raw

    def test_fail_missing_env(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        r = asyncio.run(sc.probe_03_wayland_env())
        assert r.status == "FAIL"

    def test_fail_placeholder(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/__SIGNAGE_UID__")
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        r = asyncio.run(sc.probe_03_wayland_env())
        assert r.status == "FAIL"

    def test_fail_socket_absent(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        xdg = tmp_path / "run-user"
        xdg.mkdir()
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(xdg))
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        r = asyncio.run(sc.probe_03_wayland_env())
        assert r.status == "FAIL"


# ---------------------------------------------------------------------------
# probe_04_wlr_randr
# ---------------------------------------------------------------------------

class TestProbe04:
    def test_pass(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)

        async def fake_run(*args, timeout=None):
            return (0, _WLR_JSON_OUTPUT, b"")

        monkeypatch.setattr(sc, "_run_async", fake_run)
        r = asyncio.run(sc.probe_04_wlr_randr(blocked_by=[]))
        assert r.status == "PASS"

    def test_fail_rc(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)

        async def fake_run(*args, timeout=None):
            return (1, b"", b"err")

        monkeypatch.setattr(sc, "_run_async", fake_run)
        r = asyncio.run(sc.probe_04_wlr_randr(blocked_by=[]))
        assert r.status == "FAIL"

    def test_fail_empty_outputs(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)

        async def fake_run(*args, timeout=None):
            return (0, b"[]", b"")

        monkeypatch.setattr(sc, "_run_async", fake_run)
        r = asyncio.run(sc.probe_04_wlr_randr(blocked_by=[]))
        assert r.status == "FAIL"

    def test_blocked(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        r = asyncio.run(sc.probe_04_wlr_randr(blocked_by=["03-wayland-env"]))
        assert r.status == "BLOCKED"
        assert r.blocked_by == "03-wayland-env"

    def test_pass_plain_fallback_for_0_2_x(self, tmp_path, monkeypatch):
        """wlr-randr 0.2.x doesn't support --json; must fall back to plain text."""
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        plain = (
            b'DSI-2 "(null) (null) (DSI-2)"\n'
            b'  Enabled: yes\n'
            b'  Modes:\n'
            b'    720x1280 px, 60.037998 Hz (preferred, current)\n'
        )
        calls = []

        async def fake_run(*args, timeout=None):
            calls.append(args)
            if args[:2] == ("wlr-randr", "--json"):
                return (1, b"", b"wlr-randr: unrecognized option '--json'\n")
            return (0, plain, b"")

        monkeypatch.setattr(sc, "_run_async", fake_run)
        r = asyncio.run(sc.probe_04_wlr_randr(blocked_by=[]))
        assert r.status == "PASS", f"expected PASS, got {r.status}; raw={r.raw}"
        assert "plain" in r.expected.lower()
        assert ("wlr-randr",) in [c[:1] for c in calls]


class TestParseWlrRandrText:
    def test_single_enabled_output(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        out = (
            'DSI-2 "(null) (null) (DSI-2)"\n'
            '  Enabled: yes\n'
            '  Position: 0,0\n'
        )
        outputs = sc._parse_wlr_randr_text(out)
        assert outputs == [{"name": "DSI-2", "enabled": True}]

    def test_multiple_outputs_picks_enabled(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        out = (
            'HDMI-A-1 "primary"\n'
            '  Enabled: no\n'
            'HDMI-A-2 "secondary"\n'
            '  Enabled: yes\n'
        )
        outputs = sc._parse_wlr_randr_text(out)
        assert outputs == [
            {"name": "HDMI-A-1", "enabled": False},
            {"name": "HDMI-A-2", "enabled": True},
        ]

    def test_empty(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        assert sc._parse_wlr_randr_text("") == []


class TestDiscoverWlrOutputFallback:
    def test_falls_back_to_plain_when_json_unsupported(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        plain = b'DSI-2 "..."\n  Enabled: yes\n'

        async def fake_run(*args, timeout=None):
            if args[:2] == ("wlr-randr", "--json"):
                return (1, b"", b"unrecognized option '--json'")
            return (0, plain, b"")

        monkeypatch.setattr(sc, "_run_async", fake_run)
        name = asyncio.run(sc._discover_wlr_output())
        assert name == "DSI-2"


# ---------------------------------------------------------------------------
# probe_05_sse — mock httpx + aconnect_sse
# ---------------------------------------------------------------------------

class _SseEvent:
    def __init__(self, event="message", data="x", id=""):
        self.event = event
        self.data = data
        self.id = id


def _make_sse_ctx(events, fail: Exception | None = None):
    class _SseSource:
        def __init__(self, events):
            self._events = list(events)

        def aiter_sse(self):
            outer = self

            async def gen():
                if fail is not None:
                    raise fail
                for e in outer._events:
                    yield e

            return gen()

    class _Ctx:
        async def __aenter__(self):
            return _SseSource(events)

        async def __aexit__(self, *a):
            return None

    return _Ctx()


class _FakeClient:
    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None


class TestProbe05:
    def test_pass(self, tmp_path, monkeypatch):
        sc, cache = _fresh_sidecar(tmp_path, monkeypatch)
        _write_token(cache, "tok", 0o600)
        monkeypatch.setattr(
            sc, "aconnect_sse",
            lambda client, method, url, headers=None: _make_sse_ctx([_SseEvent("ping", "")]),
        )
        monkeypatch.setattr(sc.httpx, "AsyncClient", _FakeClient)
        r = asyncio.run(sc.probe_05_sse(blocked_by=[]))
        assert r.status == "PASS", r.raw

    def test_blocked(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        r = asyncio.run(sc.probe_05_sse(blocked_by=["02-device-token"]))
        assert r.status == "BLOCKED"

    def test_fail_no_token(self, tmp_path, monkeypatch):
        # Empty token contents -> _read_token returns None -> FAIL on token-readable check
        sc, cache = _fresh_sidecar(tmp_path, monkeypatch)
        _write_token(cache, "", 0o600)
        r = asyncio.run(sc.probe_05_sse(blocked_by=[]))
        assert r.status == "FAIL"


# ---------------------------------------------------------------------------
# probe_06_apply_calibration_argv
# ---------------------------------------------------------------------------

class TestProbe06:
    def test_pass(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        # Force audio backend so wpctl path runs
        monkeypatch.setattr(sc, "_detect_audio_backend", lambda: "wpctl")
        r = asyncio.run(sc.probe_06_apply_calibration_argv())
        assert r.status == "PASS", r.raw
        assert "wlr-randr" in r.raw and "--json" in r.raw
        assert "--transform" in r.raw
        assert "1920x1080@60" in r.raw

    def test_restores_module_state(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        monkeypatch.setattr(sc, "_detect_audio_backend", lambda: "wpctl")
        sc._calibration_last_applied_at = "sentinel-ts"
        sc._wlr_output_name = "PRESET-NAME"
        sc._calibration_last_error = "sentinel-err"
        asyncio.run(sc.probe_06_apply_calibration_argv())
        assert sc._calibration_last_applied_at == "sentinel-ts"
        assert sc._wlr_output_name == "PRESET-NAME"
        assert sc._calibration_last_error == "sentinel-err"


# ---------------------------------------------------------------------------
# run_diagnostic integration
# ---------------------------------------------------------------------------

class TestRunDiagnostic:
    def test_all_pass_returns_0(self, tmp_path, monkeypatch):
        sc, cache = _fresh_sidecar(tmp_path, monkeypatch)
        _write_token(cache, "tok", 0o600)
        xdg = tmp_path / "run-user"
        xdg.mkdir()
        (xdg / "wayland-0").touch()
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(xdg))
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")

        # Patch asyncio.create_subprocess_exec at module level so probe_04 (via
        # _run_async) and probe_06 (which restores its own patch) both see a
        # fake exec. probe_06 saves/restores asyncio.create_subprocess_exec
        # around its own monkeypatch, leaving our patch intact.
        class _FakeProc:
            def __init__(self, stdout=b"", rc=0):
                self._stdout = stdout
                self.returncode = rc

            async def communicate(self):
                return self._stdout, b""

        async def fake_exec(*args, **kwargs):
            if len(args) >= 2 and args[0] == "wlr-randr" and args[1] == "--json":
                return _FakeProc(stdout=_WLR_JSON_OUTPUT)
            return _FakeProc()

        monkeypatch.setattr(sc.asyncio, "create_subprocess_exec", fake_exec)
        monkeypatch.setattr(
            sc, "aconnect_sse",
            lambda client, method, url, headers=None: _make_sse_ctx([_SseEvent("ping", "")]),
        )
        monkeypatch.setattr(sc.httpx, "AsyncClient", _FakeClient)
        monkeypatch.setattr(sc, "_detect_audio_backend", lambda: "wpctl")

        out_path = tmp_path / "transcript.md"
        rc = asyncio.run(sc.run_diagnostic(output_path=str(out_path)))
        assert rc == 0, out_path.read_text()
        text = out_path.read_text()
        assert "# Pi Calibration Diagnostic" in text
        for name in (
            "01-signage-api-base",
            "02-device-token",
            "03-wayland-env",
            "04-wlr-randr",
            "05-sse-reachability",
            "06-apply-calibration-argv",
        ):
            assert f"## Vector {name}" in text

    def test_any_fail_returns_1(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        monkeypatch.setenv("SIGNAGE_API_BASE", "")  # forces probe 01 FAIL
        rc = asyncio.run(sc.run_diagnostic(output_path=str(tmp_path / "t.md")))
        assert rc == 1

    def test_writes_to_output_path(self, tmp_path, monkeypatch):
        sc, _ = _fresh_sidecar(tmp_path, monkeypatch)
        out = tmp_path / "out.md"
        asyncio.run(sc.run_diagnostic(output_path=str(out)))
        assert out.exists()
        assert "# Pi Calibration Diagnostic" in out.read_text()
