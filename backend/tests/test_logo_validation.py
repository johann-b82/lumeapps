"""Unit tests for backend/app/security/logo_validation.py.

Covers BRAND-01 (PNG magic bytes, MIME sniff) and BRAND-02 (nh3 SVG sanitization
with reject-on-mutation).
"""
import pytest

from app.security.logo_validation import (
    PNG_SIGNATURE,
    SvgRejected,
    sanitize_svg,
    sniff_mime,
    validate_png,
)

MINIMAL_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    b'<circle cx="5" cy="5" r="4"></circle>'
    b'</svg>'
)


# --- validate_png --------------------------------------------------------

def test_validate_png_accepts_signature():
    validate_png(PNG_SIGNATURE + b"rest of file")


@pytest.mark.parametrize(
    "bad",
    [b"", b"not-a-png", b"\x89PNG", b"garbage" + PNG_SIGNATURE],
)
def test_validate_png_rejects_bad_bytes(bad):
    with pytest.raises(SvgRejected):
        validate_png(bad)


# --- sniff_mime ----------------------------------------------------------

def test_sniff_mime_png():
    assert sniff_mime(PNG_SIGNATURE + b"rest", ".png") == "image/png"


def test_sniff_mime_svg_xml_decl():
    body = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>'
    assert sniff_mime(body, ".svg") == "image/svg+xml"


def test_sniff_mime_svg_direct_tag():
    body = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
    assert sniff_mime(body, ".svg") == "image/svg+xml"


def test_sniff_mime_svg_with_bom():
    body = b"\xef\xbb\xbf<svg xmlns='http://www.w3.org/2000/svg'/>"
    assert sniff_mime(body, ".svg") == "image/svg+xml"


def test_sniff_mime_unknown_extension():
    with pytest.raises(ValueError):
        sniff_mime(b"", ".gif")


def test_sniff_mime_garbage_png():
    with pytest.raises(ValueError):
        sniff_mime(b"not a png", ".png")


def test_sniff_mime_garbage_svg():
    with pytest.raises(ValueError):
        sniff_mime(b"hello world", ".svg")


# --- sanitize_svg --------------------------------------------------------

def test_sanitize_svg_accepts_minimal():
    result = sanitize_svg(MINIMAL_SVG)
    assert result == MINIMAL_SVG


@pytest.mark.parametrize(
    "evil",
    [
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="x()"></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><a href="javascript:alert(1)">x</a></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><iframe/></foreignObject></svg>',
    ],
)
def test_sanitize_svg_rejects_malicious(evil):
    with pytest.raises(SvgRejected):
        sanitize_svg(evil)


def test_sanitize_svg_rejects_non_utf8():
    with pytest.raises(SvgRejected):
        sanitize_svg(b"\xff\xfe\x00garbage")


def test_sanitize_svg_rejects_html_comment():
    # strip_comments=True causes nh3 to mutate → byte-equality fails → reject.
    # This is the documented Pitfall 7 behavior.
    body = (
        b'<svg xmlns="http://www.w3.org/2000/svg"><!-- comment --><circle r="1"/></svg>'
    )
    with pytest.raises(SvgRejected):
        sanitize_svg(body)
