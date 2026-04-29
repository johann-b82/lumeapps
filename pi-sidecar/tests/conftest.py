"""Test fixtures for the pi sidecar.

- tmp_cache_dir: monkeypatches SIGNAGE_CACHE_DIR to a tmp path
- client: FastAPI TestClient with tmp cache + mocked SIGNAGE_API_BASE
"""
from __future__ import annotations

import os
import importlib
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def tmp_cache_dir(tmp_path, monkeypatch):
    """Patch SIGNAGE_CACHE_DIR to a fresh tmp dir; also create media/ subdir."""
    cache = tmp_path / "signage-cache"
    cache.mkdir()
    (cache / "media").mkdir()
    monkeypatch.setenv("SIGNAGE_CACHE_DIR", str(cache))
    monkeypatch.setenv("SIGNAGE_API_BASE", "http://upstream.test")
    yield cache


@pytest.fixture()
def client(tmp_cache_dir):
    """TestClient bound to a fresh sidecar app instance with isolated state."""
    # Remove any cached module so we get a fresh import with patched env.
    for key in list(sys.modules.keys()):
        if key == "sidecar" or key.startswith("sidecar."):
            del sys.modules[key]

    # Ensure pi-sidecar/ is on sys.path so `import sidecar` resolves.
    sidecar_dir = os.path.join(os.path.dirname(__file__), "..")
    sidecar_dir = os.path.abspath(sidecar_dir)
    if sidecar_dir not in sys.path:
        sys.path.insert(0, sidecar_dir)

    import sidecar as sc
    # Reset module-level state for test isolation
    sc._device_token = None
    sc._online = False
    sc._playlist_body = None
    sc._playlist_etag = None
    sc._cached_media_ids = set()

    with TestClient(sc.app, raise_server_exceptions=True) as c:
        yield c
