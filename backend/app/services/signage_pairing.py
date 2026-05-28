"""Signage pairing service — pure-function code generator + device JWT minter.

Two responsibilities:

1. Generate a 6-char human-readable pairing code drawn from a
   Crockford-derived unambiguous alphabet (D-05). Excludes the five visually
   confusing glyphs `0 O 1 I L`. Uses `secrets.choice` (cryptographically
   secure, OWASP-recommended); `random` is NOT acceptable here.

2. Mint a scoped device JWT (HS256) carrying ``{sub, scope, iat}`` — no
   ``exp`` claim. The device token is non-expiring by design: a paired
   kiosk must keep working indefinitely until an admin explicitly revokes
   it (``signage_devices.revoked_at``). Heartbeat re-issues a fresh token
   on every request so the in-flight credential stays rolling, but the
   token's *validity* is gated solely by signature + scope + revocation.

   Signing key is ``settings.SIGNAGE_DEVICE_JWT_SECRET`` — a separate
   trust domain from the Directus JWT secret.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import UUID

import jwt

from app.config import settings

# 31 chars: 8 digits + 23 letters. Excludes 0/O/1/I/L per D-05.
# U retained — in a sans-serif kiosk font it is unambiguous, and dropping
# it buys no UX gain while costing entropy.
PAIRING_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
assert len(PAIRING_ALPHABET) == 31

PAIRING_CODE_LEN = 6


def generate_pairing_code() -> str:
    """Return a 6-char uppercase pairing code. 31**6 ≈ 887M combinations."""
    return "".join(secrets.choice(PAIRING_ALPHABET) for _ in range(PAIRING_CODE_LEN))


def format_for_display(code: str) -> str:
    """Format a 6-char code as XXX-XXX for the kiosk display."""
    assert len(code) == PAIRING_CODE_LEN, "pairing code must be 6 chars"
    return f"{code[:3]}-{code[3:]}"


def mint_device_jwt(device_id: UUID) -> str:
    """Mint a non-expiring HS256 device JWT with ``scope='device'``.

    No ``exp`` claim — revocation flows exclusively through
    ``signage_devices.revoked_at`` so an unattended kiosk never silently
    drops back to the pairing screen. ``iat`` is recorded for audit.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(device_id),
        "scope": "device",
        "iat": int(now.timestamp()),
    }
    return jwt.encode(
        payload, settings.SIGNAGE_DEVICE_JWT_SECRET, algorithm="HS256"
    )
