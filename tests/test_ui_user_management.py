"""Server-rendered user-management UI tests."""

import re
import uuid

import pytest

from app.auth import USER_AUTH_ENV, WRITE_TOKEN_ENV
from app.rbac import ROLE_ADMIN, ROLE_FINANCE, ROLE_OWNER, ROLE_VIEWER
from app.services.session_service import SessionService
from app.services.user_service import UserService

CSRF_INPUT_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Start each test with auth env controls disabled."""
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)
    monkeypatch.delenv(WRITE_TOKEN_ENV, raising=False)


def _create_user_token(db_session, *, role=ROLE_OWNER):
    username = f"{role}-admin-ui-user-{uuid.uuid4().hex[:8]}"
    user = UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


def _csrf_token_from(html: str) -> str:
    match = CSRF_INPUT_RE.search(html)
    assert match is not None, html
    return match.group(1)


def test_owner_can_view_user_management_ui(client, db_session, monkeypatch):
    """Owners can view the local user-management page."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=ROLE_OWNER)

    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert "User Management" in response.text


def test_admin_can_create_user_from_ui(client, db_session, monkeypatch):
    """Admins can create a new local user through the browser UI."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=ROLE_ADMIN)
    page = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.post(
        "/admin/users",
        data={
            "username": "managed-user",
            "password": "managed-password",
            "display_name": "Managed User",
            "role": ROLE_FINANCE,
            "csrf_token": _csrf_token_from(page.text),
        },
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=False,
    )

    created = UserService.get_user_by_username(db_session, "managed-user")
    assert response.status_code == 303, response.text
    assert created is not None
    assert created.display_name == "Managed User"
    assert created.role == ROLE_FINANCE


@pytest.mark.parametrize("role", [ROLE_VIEWER, ROLE_FINANCE])
def test_non_admin_roles_cannot_access_user_management_ui(
    client,
    db_session,
    monkeypatch,
    role,
):
    """Only owner/admin roles can access user-management UI when auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=role)

    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403, response.text


def test_shared_token_can_access_user_management_ui(client, monkeypatch):
    """The shared token remains a compatibility override for automation."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = client.get(
        "/admin/users",
        headers={"X-ReleaseGuard-Token": "shared-secret"},
    )

    assert response.status_code == 200, response.text


def test_local_dev_can_view_user_management_when_auth_unset(client):
    """Local-dev behavior is unchanged when user auth is not required."""
    response = client.get("/admin/users")

    assert response.status_code == 200, response.text
