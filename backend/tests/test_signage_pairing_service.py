"""Unit tests for app.services.signage_pairing — SGN-BE-04 foundations."""
from __future__ import annotations

import re
import time
from uuid import uuid4

import jwt
import pytest

from app.config import settings
from app.services.signage_pairing import (
    DEVICE_JWT_TTL_HOURS,
    PAIRING_ALPHABET,
    PAIRING_CODE_LEN,
    format_for_display,
    generate_pairing_code,
    mint_device_jwt,
)

_CODE_RE = re.compile(rf"^[{re.escape(PAIRING_ALPHABET)}]{{{PAIRING_CODE_LEN}}}$")


def test_pairing_alphabet_shape():
    # D-05: 31 chars, no visually confusing glyphs.
    assert len(PAIRING_ALPHABET) == 31
    for bad in ("0", "1", "O", "I", "L"):
        assert bad not in PAIRING_ALPHABET, f"alphabet must not contain {bad!r}"


def test_generate_pairing_code_shape():
    code = generate_pairing_code()
    assert len(code) == 6
    assert _CODE_RE.match(code), f"code {code!r} contains out-of-alphabet chars"


def test_format_for_display():
    assert format_for_display("ABC234") == "ABC-234"
    assert format_for_display("23456H") == "234-56H"


def test_format_for_display_wrong_length_asserts():
    with pytest.raises(AssertionError):
        format_for_display("TOO")


def test_generate_pairing_code_consecutive_differ():
    # Probabilistic — collision chance is ~1/887M per pair; vanishingly small.
    a = generate_pairing_code()
    b = generate_pairing_code()
    assert a != b


def test_mint_device_jwt_roundtrip():
    device_id = uuid4()
    token = mint_device_jwt(device_id)
    assert isinstance(token, str) and token

    payload = jwt.decode(
        token, settings.SIGNAGE_DEVICE_JWT_SECRET, algorithms=["HS256"]
    )
    assert payload["sub"] == str(device_id)
    assert payload["scope"] == "device"
    assert "iat" in payload and "exp" in payload

    # exp is roughly iat + 24h
    assert payload["exp"] - payload["iat"] == DEVICE_JWT_TTL_HOURS * 3600

    # iat is within ±5s of "now"
    now = int(time.time())
    assert abs(now - payload["iat"]) <= 5


def test_mint_device_jwt_rejects_wrong_secret():
    token = mint_device_jwt(uuid4())
    with pytest.raises(jwt.PyJWTError):
        jwt.decode(token, "wrong-secret", algorithms=["HS256"])
