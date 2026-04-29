"""Logo upload validation (BRAND-01) and SVG sanitization (BRAND-02).

Two gates, applied in the router before persistence:
  - validate_png / sniff_mime: magic-byte check so we don't trust Content-Type
  - sanitize_svg: nh3 with an explicit SVG allowlist + reject-on-mutation

Per D-13: if nh3.clean() mutates the bytes, the upload is rejected as 422.
Per Pitfall 1: nh3's default ALLOWED_TAGS set contains ZERO SVG elements —
we MUST pass an explicit tags= kwarg. Failure to do so strips every SVG to
empty and makes every legitimate upload fail.
"""
from __future__ import annotations

import nh3

# --- PNG magic bytes -----------------------------------------------------
# Canonical 8-byte PNG signature: 89 50 4E 47 0D 0A 1A 0A
PNG_SIGNATURE: bytes = b"\x89PNG\r\n\x1a\n"


# --- SVG allowlist (explicit — see Pitfall 1) ----------------------------
SVG_ALLOWED_TAGS: set[str] = {
    "svg", "g", "defs", "symbol", "use",
    "title", "desc",
    "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "text", "tspan",
    "linearGradient", "radialGradient", "stop",
    "clipPath", "mask",
}

SVG_ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "svg": {"xmlns", "viewBox", "width", "height", "fill", "stroke",
            "preserveAspectRatio", "version"},
    "g": {"transform", "fill", "stroke", "opacity", "clip-path", "mask"},
    "path": {"d", "fill", "stroke", "stroke-width", "stroke-linecap",
             "stroke-linejoin", "fill-rule", "clip-rule", "transform", "opacity"},
    "rect": {"x", "y", "width", "height", "rx", "ry", "fill", "stroke",
             "stroke-width", "transform", "opacity"},
    "circle": {"cx", "cy", "r", "fill", "stroke", "stroke-width",
               "transform", "opacity"},
    "ellipse": {"cx", "cy", "rx", "ry", "fill", "stroke", "stroke-width",
                "transform", "opacity"},
    "line": {"x1", "y1", "x2", "y2", "stroke", "stroke-width", "transform"},
    "polyline": {"points", "fill", "stroke", "stroke-width", "transform"},
    "polygon": {"points", "fill", "stroke", "stroke-width", "transform"},
    "text": {"x", "y", "dx", "dy", "font-family", "font-size", "fill",
             "text-anchor", "transform"},
    "tspan": {"x", "y", "dx", "dy", "font-family", "font-size", "fill"},
    "linearGradient": {"id", "x1", "y1", "x2", "y2", "gradientUnits",
                       "gradientTransform"},
    "radialGradient": {"id", "cx", "cy", "r", "fx", "fy", "gradientUnits",
                       "gradientTransform"},
    "stop": {"offset", "stop-color", "stop-opacity"},
    "clipPath": {"id", "clipPathUnits"},
    "mask": {"id", "maskUnits", "x", "y", "width", "height"},
    "use": {"href", "x", "y", "width", "height", "transform"},  # href only; NO xlink:href
    "symbol": {"id", "viewBox"},
    "title": set(),
    "desc": set(),
}

# D-12: NO javascript:, NO data: — https only (and no URIs at all in practice,
# since most allowed attributes don't take a URL).
SVG_ALLOWED_URL_SCHEMES: set[str] = {"https"}


class SvgRejected(Exception):
    """Raised when an upload fails validation (PNG magic byte check OR
    nh3 mutated the SVG bytes OR SVG was not valid UTF-8).
    """


def validate_png(raw: bytes) -> None:
    """Assert bytes start with the PNG magic signature.

    Per D-14: no re-encoding in v1.1 — we just confirm the header.
    Per D-17: do NOT trust client Content-Type; only the magic bytes.
    """
    if not raw.startswith(PNG_SIGNATURE):
        raise SvgRejected("File is not a valid PNG (missing PNG signature)")


def sanitize_svg(raw_bytes: bytes) -> bytes:
    """Return raw_bytes unchanged iff nh3 did not mutate them; else raise.

    Per D-13 (reject-on-mutation): the diff strategy is byte-equality on the
    UTF-8 text representation. Over-rejection (e.g. whitespace-normalised SVGs
    from Illustrator) is preferable to under-rejection — the 422 error tells
    the user to re-export without comments.
    """
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SvgRejected("SVG must be valid UTF-8") from exc

    cleaned = nh3.clean(
        raw_text,
        tags=SVG_ALLOWED_TAGS,
        attributes=SVG_ALLOWED_ATTRIBUTES,
        url_schemes=SVG_ALLOWED_URL_SCHEMES,
        strip_comments=True,
    )
    if cleaned != raw_text:
        raise SvgRejected(
            "SVG contained disallowed content and was rejected. "
            "Remove comments, scripts, and event handlers, then re-upload."
        )
    return raw_bytes


def sniff_mime(raw: bytes, ext: str) -> str:
    """Return canonical MIME type for (raw, ext) or raise ValueError.

    Per D-15: only .png and .svg are allowed (case-insensitive handled by caller).
    Per D-17: bytes sniffing overrides any client-declared Content-Type.
    """
    if ext == ".png":
        if not raw.startswith(PNG_SIGNATURE):
            raise ValueError("File is not a valid PNG")
        return "image/png"
    if ext == ".svg":
        stripped = raw.lstrip()
        if stripped.startswith(b"\xef\xbb\xbf"):  # UTF-8 BOM
            stripped = stripped[3:].lstrip()
        if not (stripped.startswith(b"<?xml") or stripped.startswith(b"<svg")):
            raise ValueError("File is not a valid SVG")
        return "image/svg+xml"
    raise ValueError(f"Unsupported extension: {ext}")
