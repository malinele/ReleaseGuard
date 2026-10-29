"""CSRF protection tests for server-rendered UI POST forms."""

import re
import uuid

import pytest

from app.auth import USER_AUTH_ENV
from app.rbac import ROLE_ADMIN
from app.services.session_service import SessionService
from app.services.user_service import UserService


CSRF_INPUT_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Start each test with auth env controls disabled."""
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)


def _csrf_token_from(html: str) -> str:
    match = CSRF_INPUT_RE.search(html)
    assert match is not None, html
    return match.group(1)


def _create_user(db_session, *, role=ROLE_ADMIN):
    username = f"csrf-user-{uuid.uuid4().hex[:8]}"
    return UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
        role=role,
    )


def _login_with_csrf(client, username: str = "ui-user"):
    login_page = client.get("/login")
    token = _csrf_token_from(login_page.text)
    return client.post(
        "/login",
        data={
            "username": username,
            "password": "correct-password",
            "csrf_token": token,
        },
        follow_redirects=False,
    )


def test_login_form_includes_csrf_token(client, monkeypatch):
    """Login form emits a CSRF token before authentication exists."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.get("/login")

    assert response.status_code == 200, response.text
    assert _csrf_token_from(response.text)


def test_login_post_without_csrf_token_is_rejected(client, db_session, monkeypatch):
    """Credential POSTs must include the form CSRF token."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    UserService.create_user(
        db_session,
        username="ui-user",
        password="correct-password",
    )
    client.get("/login")

    response = client.post(
        "/login",
        data={"username": "ui-user", "password": "correct-password"},
        follow_redirects=False,
    )

    assert response.status_code == 403, response.text


def test_login_post_with_csrf_token_succeeds(client, db_session, monkeypatch):
    """A matching CSRF token allows the existing login flow."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    UserService.create_user(
        db_session,
        username="ui-user",
        password="correct-password",
    )

    response = _login_with_csrf(client)

    assert response.status_code == 303, response.text


def test_logout_without_csrf_token_is_rejected(client, db_session, monkeypatch):
    """Logout must not be triggerable by a cross-site POST."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    UserService.create_user(
        db_session,
        username="ui-user",
        password="correct-password",
    )
    assert _login_with_csrf(client).status_code == 303

    response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 403, response.text


def test_logout_with_csrf_token_succeeds(client, db_session, monkeypatch):
    """A matching CSRF token preserves the existing logout behavior."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    UserService.create_user(
        db_session,
        username="ui-user",
        password="correct-password",
    )
    assert _login_with_csrf(client).status_code == 303
    dashboard = client.get("/")
    token = _csrf_token_from(dashboard.text)

    response = client.post(
        "/logout",
        data={"csrf_token": token},
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text


def test_admin_user_create_without_csrf_token_is_rejected(
    client,
    db_session,
    monkeypatch,
):
    """The admin user-management POST must require CSRF protection."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    user = _create_user(db_session)
    token = SessionService.create_session(db_session, user_id=user.id).token
    client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.post(
        "/admin/users",
        data={
            "username": "managed-user",
            "password": "managed-password",
            "role": "viewer",
        },
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=False,
    )

    assert response.status_code == 403, response.text


def test_admin_user_create_with_csrf_token_succeeds(
    client,
    db_session,
    monkeypatch,
):
    """A matching CSRF token allows the existing admin user creation flow."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    user = _create_user(db_session)
    session_token = SessionService.create_session(db_session, user_id=user.id).token
    page = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    csrf_token = _csrf_token_from(page.text)

    response = client.post(
        "/admin/users",
        data={
            "username": "managed-user",
            "password": "managed-password",
            "role": "viewer",
            "csrf_token": csrf_token,
        },
        headers={"Authorization": f"Bearer {session_token}"},
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
