from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    VIEWER = "viewer"
    # QS: interim module-scoped role (FAIR + ATR only). Fest verdrahtet bis
    # zum AD-basierten Rechtesystem; siehe require_atr_fair in directus_auth.py.
    QS = "qs"
