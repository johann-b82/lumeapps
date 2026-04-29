"""Signage pairing service — pure-function code generator + device JWT minter.

Two responsibilities:

1. Generate a 6-char human-readable pairing code drawn from a
   Crockford-derived unambiguous alphabet (D-05). Excludes the five visually
   confusing glyphs `0 O 1 I L`. Uses `secrets.choice` (cryptographically
   secure, OWASP-recommended); `random` is NOT acceptable here.

2. Mint a scoped device JWT (HS256) carrying `{sub, scope, iat, exp}` per
   D-01. Signing key is `settings.SIGNAGE_DEVICE_JWT_SECRET` — a separate
   trust domain from the Directus JWT secret.

Token TTL: 24h (D-01). Re-issuance happens on future heartbeat rotation
(Phase 43+); Phase 42 just mints the initial token on claim.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from app.config import settings

# 31 chars: 8 digits + 23 letters. Excludes 0/O/1/I/L per D-05.
# U retained — in a sans-serif kiosk font it is unambiguous, and dropping
# it buys no UX gain while costing entropy.
PAIRING_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
assert len(PAIRING_ALPHABET) == 31

PAIRING_CODE_LEN = 6

# D-01: 24-hour device JWT TTL.
DEVICE_JWT_TTL_HOURS = 24


def generate_pairing_code() -> str:
    """Return a 6-char uppercase pairing code. 31**6 ≈ 887M combinations."""
    return "".join(secrets.choice(PAIRING_ALPHABET) for _ in range(PAIRING_CODE_LEN))


def format_for_display(code: str) -> str:
    """Format a 6-char code as XXX-XXX for the kiosk display."""
    assert len(code) == PAIRING_CODE_LEN, "pairing code must be 6 chars"
    return f"{code[:3]}-{code[3:]}"


def mint_device_jwt(device_id: UUID) -> str:
    """Mint an HS256 device JWT with scope='device' and a 24h TTL (D-01)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(device_id),
        "scope": "device",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=DEVICE_JWT_TTL_HOURS)).timestamp()),
    }
    return jwt.encode(
        payload, settings.SIGNAGE_DEVICE_JWT_SECRET, algorithm="HS256"
    )
