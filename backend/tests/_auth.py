"""Shared Directus JWT mint helper for tests.

Promoted from `test_directus_auth.py` (v1.24 A-1) so non-test modules —
specifically `conftest.py` fixtures — can import it without dragging in
the auth-test module's own fixtures and parametrized cases.
"""
import os
from datetime import datetime, timedelta, timezone

import jwt

DIRECTUS_SECRET = os.environ["DIRECTUS_SECRET"]
ADMIN_UUID = os.environ["DIRECTUS_ADMINISTRATOR_ROLE_UUID"]
VIEWER_UUID = os.environ["DIRECTUS_VIEWER_ROLE_UUID"]
USER_UUID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def mint(
    role_uuid: str,
    *,
    secret: str = DIRECTUS_SECRET,
    exp_minutes: int = 15,
    user_id: str = USER_UUID,
    extra: dict | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "id": user_id,
        "role": role_uuid,
        "app_access": True,
        "admin_access": True,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_minutes)).timestamp()),
        "iss": "directus",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm="HS256")
