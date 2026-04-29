import pytest
from fastapi import HTTPException
from app.security.directus_auth import require_admin
from app.security.roles import Role
from app.schemas import CurrentUser


def _user(role: Role) -> CurrentUser:
    return CurrentUser(id="00000000-0000-0000-0000-000000000001", email="t@example.com", role=role)


def test_require_admin_allows_admin():
    u = _user(Role.ADMIN)
    assert require_admin(current_user=u) is u


def test_require_admin_rejects_viewer():
    u = _user(Role.VIEWER)
    with pytest.raises(HTTPException) as excinfo:
        require_admin(current_user=u)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "admin role required"
