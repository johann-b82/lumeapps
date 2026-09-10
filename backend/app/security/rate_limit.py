"""In-process sliding-window rate limiter (D-09).

Design:
    - {ip: deque[float monotonic-timestamps]} bucketed per client IP,
      one bucket dict per limiter instance
    - Prune entries older than the window on every hit
    - Reject with 429 + Retry-After when the window is full
    - Guarded by a single asyncio.Lock — single-process correctness

-----------------------------------------------------------------------------
CROSS-CUTTING INVARIANT: this dependency is only correct under `--workers 1`.
With N uvicorn workers each worker would keep its own in-memory buckets,
so the effective limit becomes N * limit per IP. APScheduler also requires
`--workers 1` (see docker-compose.yml `api` service command). Do NOT remove
the `--workers 1` flag without first porting this limiter to a shared store
(Redis / postgres row) AND extracting the scheduler to its own process.
-----------------------------------------------------------------------------

Client-IP source (D-10):
    Caddy sits in front of the api container and *appends* the peer address
    to X-Forwarded-For, so the LAST element of that header is the address
    that actually opened the connection to Caddy. A client can prepend its
    own entries, but it cannot remove Caddy's — therefore only the last
    element is usable, and only when the direct TCP peer is itself trusted.
    Trust is decided by TRUSTED_PROXY_NETS (comma-separated CIDRs, default:
    the private ranges the compose network lives in). Without that guard the
    header would be trivially spoofable; without the header at all every
    request behind Caddy shares one bucket, which is how the pairing limit
    used to be effectively global.
"""
from __future__ import annotations

import asyncio
import ipaddress
import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_DEFAULT_PROXY_NETS = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8,::1/128"


def _trusted_nets() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    roh = os.getenv("TRUSTED_PROXY_NETS", _DEFAULT_PROXY_NETS)
    netze = []
    for teil in roh.split(","):
        teil = teil.strip()
        if not teil:
            continue
        try:
            netze.append(ipaddress.ip_network(teil, strict=False))
        except ValueError:
            continue
    return tuple(netze)


def _ist_vertrauenswuerdig(host: str) -> bool:
    try:
        adresse = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(adresse in netz for netz in _trusted_nets())


def _client_ip(request: Request) -> str:
    """Address of the real caller — see the module docstring on X-Forwarded-For."""
    peer = request.client.host if request.client else ""
    if peer and _ist_vertrauenswuerdig(peer):
        weitergereicht = request.headers.get("x-forwarded-for", "")
        if weitergereicht:
            letzter = weitergereicht.split(",")[-1].strip()
            if letzter:
                return letzter
    return peer or "unknown"


class Begrenzer:
    """A named sliding-window limit, usable as a FastAPI dependency."""

    def __init__(self, name: str, *, limit: int, window_s: float = 60.0) -> None:
        self.name = name
        self.limit = limit
        self.window_s = window_s
        self._buckets: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=limit + 1)
        )
        self._lock = asyncio.Lock()
        _registry.append(self)

    async def __call__(self, request: Request) -> None:
        now = time.monotonic()
        ip = _client_ip(request)
        async with self._lock:
            window = self._buckets[ip]
            while window and (now - window[0]) > self.window_s:
                window.popleft()
            if len(window) >= self.limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"too many {self.name} requests from this IP",
                    headers={"Retry-After": str(int(self.window_s))},
                )
            window.append(now)

    def _reset(self) -> None:
        self._buckets.clear()


_registry: list[Begrenzer] = []

rate_limit_pair_request = Begrenzer("pairing", limit=5)
"""5 pairing requests / 60s per IP."""

rate_limit_embed_photo = Begrenzer("embed photo", limit=60)
"""60 kiosk photo fetches / 60s per IP — a board shows two tiles per page."""


def _reset_for_tests() -> None:
    """Test-only helper: clear all per-IP buckets of every limiter."""
    for begrenzer in _registry:
        begrenzer._reset()
