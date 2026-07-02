"""Directus file helpers for the FAIR module (v1.63).

``upload_drawing_to_directus`` streams a PDF/PNG/JPG multipart body into
Directus ``/files`` with a 50MB hard cap (enforced as bytes arrive, never
buffering the whole body). ``fetch_directus_asset`` downloads a stored asset
back from Directus with the admin token so the backend can proxy it to the
authenticated SPA (``GET /api/fair/projects/{id}/file``) — no public Directus
exposure required.

Mirrors ``app.services.directus_uploads`` for the upload half.
"""
from __future__ import annotations

import logging
import tempfile
from typing import AsyncIterator

import httpx
from fastapi import HTTPException

from app.config import settings

log = logging.getLogger(__name__)

# Hard product cap on raw drawing uploads (matches the signage 50MB cap).
MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024

_DIRECTUS_TIMEOUT_S: float = 120.0
_RESPONSE_SNIPPET_BYTES: int = 2048


async def upload_drawing_to_directus(
    filename: str,
    content_type: str,
    body_stream: AsyncIterator[bytes],
) -> tuple[str, int]:
    """Stream ``body_stream`` into Directus ``/files``; return ``(uuid, total_bytes)``.

    Raises:
        HTTPException(413): if the body exceeds ``MAX_UPLOAD_BYTES``.
        HTTPException(502): if Directus rejects the upload or is unreachable.
    """
    total_bytes = 0
    spool = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024)
    try:
        async for chunk in body_stream:
            if not chunk:
                continue
            total_bytes += len(chunk)
            if total_bytes > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413, detail="drawing upload exceeds 50MB cap"
                )
            spool.write(chunk)
        spool.seek(0)

        url = f"{settings.DIRECTUS_URL.rstrip('/')}/files"
        headers = {"Authorization": f"Bearer {settings.DIRECTUS_ADMIN_TOKEN}"}
        files = {"file": (filename, spool, content_type)}

        try:
            async with httpx.AsyncClient(timeout=_DIRECTUS_TIMEOUT_S) as http:
                response = await http.post(url, headers=headers, files=files)
        except httpx.HTTPError as exc:
            log.warning("directus drawing upload transport error: %s", exc)
            raise HTTPException(
                status_code=502, detail="directus upload failed"
            ) from exc
    finally:
        spool.close()

    if response.status_code // 100 != 2:
        log.warning(
            "directus drawing upload non-2xx: status=%s body=%s",
            response.status_code,
            response.text[:_RESPONSE_SNIPPET_BYTES],
        )
        raise HTTPException(status_code=502, detail="directus upload failed")

    try:
        directus_file_uuid = response.json()["data"]["id"]
    except (ValueError, KeyError, TypeError) as exc:
        log.warning(
            "directus drawing upload: could not parse response id: %s body=%s",
            exc,
            response.text[:_RESPONSE_SNIPPET_BYTES],
        )
        raise HTTPException(
            status_code=502, detail="directus upload failed"
        ) from exc

    return directus_file_uuid, total_bytes


async def fetch_directus_asset(file_uuid: str) -> tuple[bytes, str]:
    """Download a stored Directus asset; return ``(content, content_type)``.

    Raises:
        HTTPException(404): if Directus reports the asset is gone.
        HTTPException(502): on any other Directus error or transport failure.
    """
    url = f"{settings.DIRECTUS_URL.rstrip('/')}/assets/{file_uuid}"
    headers = {"Authorization": f"Bearer {settings.DIRECTUS_ADMIN_TOKEN}"}
    try:
        async with httpx.AsyncClient(timeout=_DIRECTUS_TIMEOUT_S) as http:
            response = await http.get(url, headers=headers)
    except httpx.HTTPError as exc:
        log.warning("directus asset fetch transport error: %s", exc)
        raise HTTPException(status_code=502, detail="directus asset fetch failed") from exc

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="drawing file not found")
    if response.status_code // 100 != 2:
        log.warning(
            "directus asset fetch non-2xx: status=%s body=%s",
            response.status_code,
            response.text[:_RESPONSE_SNIPPET_BYTES],
        )
        raise HTTPException(status_code=502, detail="directus asset fetch failed")

    content_type = response.headers.get("content-type", "application/octet-stream")
    return response.content, content_type
