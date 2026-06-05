"""Directus file-upload helper (SGN-BE-07/08 — Phase 44).

Streams a multipart body into Directus `/files` with a 50MB hard cap
(CONTEXT D-13) enforced as bytes arrive — never buffers the full body
into memory. Returns the Directus file UUID on success; raises
HTTPException(413) when the cap is exceeded and HTTPException(502) when
Directus rejects the upload.

Consumed by plan 44-03's POST /api/signage/media/pptx endpoint.
"""
from __future__ import annotations

import logging
import tempfile
from typing import AsyncIterator

import httpx
from fastapi import HTTPException

from app.config import settings

log = logging.getLogger(__name__)

# D-13: hard product cap on raw PPTX uploads.
MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024

# Upstream Directus request budget — generous enough for a 50MB file over a
# compose-internal link but still bounded so the backend task doesn't wedge.
_DIRECTUS_TIMEOUT_S: float = 120.0

# Max stderr/response snippet length tolerated in the failure log (keeps
# secret tokens and long HTML error pages out of logs).
_RESPONSE_SNIPPET_BYTES: int = 2048


async def upload_pptx_to_directus(
    filename: str,
    content_type: str,
    body_stream: AsyncIterator[bytes],
) -> tuple[str, int]:
    """Stream ``body_stream`` into Directus ``/files``; return ``(directus_file_uuid, total_bytes)``.

    Enforces the 50MB cap (``MAX_UPLOAD_BYTES``) by tallying bytes as they
    arrive and raising ``HTTPException(413)`` the moment the running total
    would exceed the cap. The body is never fully read into memory.

    Raises:
        HTTPException(413): if the uploaded body exceeds 50MB.
        HTTPException(502): if Directus returns a non-2xx response.
    """
    total_bytes = 0

    # Spool the request body into a SpooledTemporaryFile: in-memory up to 10MB
    # (the typical small-deck case), automatic spill to a tempfile on disk past
    # that. httpx's multipart `files=` parameter wants a sync file-like object
    # with `.read(n)` — an async generator does not satisfy that contract and
    # blows up inside _multipart.render_data() with AttributeError.
    # The 50MB cap is enforced byte-by-byte as data arrives, BEFORE the buffer
    # is handed to httpx.
    spool = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024)
    try:
        async for chunk in body_stream:
            if not chunk:
                continue
            total_bytes += len(chunk)
            if total_bytes > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="pptx upload exceeds 50MB cap",
                )
            spool.write(chunk)
        spool.seek(0)

        url = f"{settings.DIRECTUS_URL.rstrip('/')}/files"
        headers = {
            "Authorization": f"Bearer {settings.DIRECTUS_ADMIN_TOKEN}",
        }
        files = {
            "file": (filename, spool, content_type),
        }

        try:
            async with httpx.AsyncClient(timeout=_DIRECTUS_TIMEOUT_S) as http:
                response = await http.post(url, headers=headers, files=files)
        except httpx.HTTPError as exc:
            log.warning("directus upload transport error: %s", exc)
            raise HTTPException(
                status_code=502, detail="directus upload failed"
            ) from exc
    finally:
        spool.close()

    if response.status_code // 100 != 2:
        snippet = response.text[:_RESPONSE_SNIPPET_BYTES]
        log.warning(
            "directus upload non-2xx: status=%s body=%s",
            response.status_code,
            snippet,
        )
        raise HTTPException(status_code=502, detail="directus upload failed")

    try:
        payload = response.json()
        directus_file_uuid = payload["data"]["id"]
    except (ValueError, KeyError, TypeError) as exc:
        log.warning(
            "directus upload: could not parse response id: %s body=%s",
            exc,
            response.text[:_RESPONSE_SNIPPET_BYTES],
        )
        raise HTTPException(
            status_code=502, detail="directus upload failed"
        ) from exc

    return directus_file_uuid, total_bytes
