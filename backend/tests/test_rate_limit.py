"""Tests for app.security.rate_limit.rate_limit_pair_request — D-09."""
from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.security import rate_limit as rl_mod
from app.security.rate_limit import rate_limit_pair_request


@pytest.fixture(autouse=True)
def _clear_buckets():
    rl_mod._reset_for_tests()
    yield
    rl_mod._reset_for_tests()


@pytest.fixture
def app():
    a = FastAPI()

    @a.post("/_test/rate-limited", dependencies=[Depends(rate_limit_pair_request)])
    async def rl():
        return {"ok": True}

    return a


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("1.2.3.4", 12345)),
        base_url="http://test",
    ) as c:
        yield c


async def test_five_calls_allowed(client):
    for i in range(5):
        r = await client.post("/_test/rate-limited")
        assert r.status_code == 200, f"call {i + 1} failed: {r.text}"


async def test_sixth_call_returns_429_with_retry_after(client):
    for _ in range(5):
        r = await client.post("/_test/rate-limited")
        assert r.status_code == 200
    r = await client.post("/_test/rate-limited")
    assert r.status_code == 429
    assert r.headers.get("retry-after") == "60"
    assert r.json()["detail"] == "too many pairing requests from this IP"


async def test_different_ips_dont_share_window(app):
    # Two separate clients with different source IPs — each gets its own bucket.
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("10.0.0.1", 1111)),
        base_url="http://test",
    ) as c1:
        for _ in range(5):
            assert (await c1.post("/_test/rate-limited")).status_code == 200
        assert (await c1.post("/_test/rate-limited")).status_code == 429

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("10.0.0.2", 2222)),
        base_url="http://test",
    ) as c2:
        # Fresh IP → fresh window
        assert (await c2.post("/_test/rate-limited")).status_code == 200


async def test_window_resets_after_elapse(client, monkeypatch):
    # Drive the limiter's time.monotonic() explicitly so we can jump forward.
    import time as time_mod

    fake_now = {"t": 1000.0}

    def _fake_monotonic():
        return fake_now["t"]

    monkeypatch.setattr(rl_mod.time, "monotonic", _fake_monotonic)
    # Sanity — we really did swap it
    assert rl_mod.time.monotonic() == 1000.0
    _ = time_mod  # keep import referenced for linters

    for _ in range(5):
        assert (await client.post("/_test/rate-limited")).status_code == 200
    assert (await client.post("/_test/rate-limited")).status_code == 429

    # Jump past the window — 5 pruned → new call allowed.
    fake_now["t"] += 61.0
    assert (await client.post("/_test/rate-limited")).status_code == 200


# --- Befund 6: echte Absender-IP hinter Caddy -------------------------------


async def test_hinter_vertrauenswuerdigem_proxy_zaehlt_die_letzte_xff_adresse(app):
    """Caddy hängt den echten Peer hinten an — genau der bekommt seinen Eimer.

    Ohne das teilten sich alle Clients hinter Caddy ein einziges Fenster: das
    Limit war faktisch global.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("172.18.0.5", 5000)),
        base_url="http://test",
    ) as c:
        for _ in range(5):
            r = await c.post("/_test/rate-limited", headers={"X-Forwarded-For": "10.9.0.1"})
            assert r.status_code == 200
        assert (
            await c.post("/_test/rate-limited", headers={"X-Forwarded-For": "10.9.0.1"})
        ).status_code == 429
        # Anderer Absender, gleicher Proxy → eigenes Fenster.
        assert (
            await c.post("/_test/rate-limited", headers={"X-Forwarded-For": "10.9.0.2"})
        ).status_code == 200


async def test_selbst_gesetztes_xff_kann_das_fenster_nicht_wechseln(app):
    """Ein Client, der selbst X-Forwarded-For schickt, hängt hinter Caddy immer
    noch am Ende der Liste — nur der letzte Eintrag zählt."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("172.18.0.5", 5000)),
        base_url="http://test",
    ) as c:
        for i in range(5):
            r = await c.post(
                "/_test/rate-limited",
                headers={"X-Forwarded-For": f"203.0.113.{i}, 10.9.0.7"},
            )
            assert r.status_code == 200
        r = await c.post(
            "/_test/rate-limited",
            headers={"X-Forwarded-For": "203.0.113.99, 10.9.0.7"},
        )
        assert r.status_code == 429


async def test_ohne_vertrauenswuerdigen_peer_wird_xff_ignoriert(app):
    """Direkt aus dem Internet angesprochen ist der Header wertlos."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("198.51.100.7", 4000)),
        base_url="http://test",
    ) as c:
        for i in range(5):
            r = await c.post(
                "/_test/rate-limited", headers={"X-Forwarded-For": f"10.9.0.{i}"}
            )
            assert r.status_code == 200
        r = await c.post("/_test/rate-limited", headers={"X-Forwarded-For": "10.9.0.99"})
        assert r.status_code == 429
