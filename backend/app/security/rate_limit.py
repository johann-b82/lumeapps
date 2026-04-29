"""In-process sliding-window rate limiter for /pair/request (D-09).

Design:
    - {ip: deque[float monotonic-timestamps]} bucketed per client IP
    - Prune entries older than _WINDOW_S on every hit
    - Reject with 429 + Retry-After when the window is full (>= _LIMIT)
    - Guarded by a single asyncio.Lock — single-process correctness

-----------------------------------------------------------------------------
CROSS-CUTTING INVARIANT: this dependency is only correct under `--workers 1`.
With N uvicorn workers each worker would keep its own in-memory `_buckets`,
so the effective limit becomes N * _LIMIT per IP. APScheduler also requires
`--workers 1` (see docker-compose.yml `api` service command). Do NOT remove
the `--workers 1` flag without first porting this limiter to a shared store
(Redis / postgres row) AND extracting the scheduler to its own process.
-----------------------------------------------------------------------------

Client-IP source (D-10):
    - Uses `request.client.host`. The dev / compose topology has no reverse
      proxy in front of the api container, so this is the Pi's true IP.
    - TODO (production): if a reverse proxy (nginx / Traefik / Cloudflare) is
      ever introduced, `_client_ip` MUST be updated to parse X-Forwarded-For
      with a trusted-proxy allowlist. Anything else is trivially spoofable
      (a client can send its own X-Forwarded-For header today).
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_WINDOW_S = 60.0
_LIMIT = 5

# bounded per-IP deque; entries are monotonic() timestamps
_buckets: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_LIMIT + 1))
_lock = asyncio.Lock()


def _client_ip(request: Request) -> str:
    # D-10: direct TCP peer. See module docstring for reverse-proxy guidance.
    return request.client.host if request.client else "unknown"


async def rate_limit_pair_request(request: Request) -> None:
    """FastAPI dependency: raise 429 when caller exceeds 5 req / 60s per IP."""
    now = time.monotonic()
    ip = _client_ip(request)
    async with _lock:
        window = _buckets[ip]
        # Prune entries older than the window
        while window and (now - window[0]) > _WINDOW_S:
            window.popleft()
        if len(window) >= _LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="too many pairing requests from this IP",
                headers={"Retry-After": str(int(_WINDOW_S))},
            )
        window.append(now)


def _reset_for_tests() -> None:
    """Test-only helper: clear all per-IP buckets."""
    _buckets.clear()
