"""Browser login/logout tests for server-rendered UI routes."""

import re

import pytest

from app.auth import USER_AUTH_ENV, WRITE_TOKEN_ENV
from app.services.user_service import UserService
from app.ui.routes import UI_SESSION_COOKIE

CSRF_INPUT_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Start each test with auth env controls disabled."""
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)
    monkeypatch.delenv(WRITE_TOKEN_ENV, raising=False)


def _create_user(db_session, username="ui-user", password="correct-password"):
    return UserService.create_user(
        db_session,
        username=username,
        password=password,
        display_name="UI User",
    )


def _csrf_token_from(html: str) -> str:
    match = CSRF_INPUT_RE.search(html)
    assert match is not None, html
    return match.group(1)


def _login(client, username="ui-user", password="correct-password"):
    login_page = client.get("/login")
    return client.post(
        "/login",
        data={
            "username": username,
            "password": password,
            "csrf_token": _csrf_token_from(login_page.text),
        },
        follow_redirects=False,
    )


def test_get_login_page_reachable_when_user_auth_required(client, monkeypatch):
    """The login page stays reachable when UI auth is required."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.get("/login")

    assert response.status_code == 200, response.text
    assert "Sign in" in response.text


def test_post_login_bad_credentials_does_not_set_cookie(client, db_session, monkeypatch):
    """Bad UI credentials return 401 and do not create the UI session cookie."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    _create_user(db_session)

    response = _login(client, password="wrong-password")

    assert response.status_code == 401, response.text
    assert UI_SESSION_COOKIE not in response.cookies
    assert "Invalid username or password" in response.text


def test_post_login_valid_credentials_sets_cookie_and_grants_projects(
    client,
    db_session,
    sample_project,
    monkeypatch,
):
    """Valid credentials create a cookie session usable by protected UI pages."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    _create_user(db_session)

    login_response = _login(client)
    projects_response = client.get("/projects")

    assert login_response.status_code == 303, login_response.text
    assert UI_SESSION_COOKIE in login_response.cookies
    assert projects_response.status_code == 200, projects_response.text
    assert sample_project["name"] in projects_response.text


def test_post_logout_revokes_session(client, db_session, monkeypatch):
    """Logout revokes the cookie-backed session and protected UI access fails."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    _create_user(db_session)
    login_response = _login(client)

    assert login_response.status_code == 303
    assert client.get("/projects").status_code == 200

    projects_page = client.get("/projects")
    logout_response = client.post(
        "/logout",
        data={"csrf_token": _csrf_token_from(projects_page.text)},
        follow_redirects=False,
    )
    projects_response = client.get("/projects")

    assert logout_response.status_code == 303, logout_response.text
    assert projects_response.status_code == 401, projects_response.text


def test_existing_shared_token_still_allows_ui_when_auth_required(
    client,
    sample_project,
    monkeypatch,
):
    """The existing shared token remains compatible with UI auth enforcement."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = client.get(
        f"/projects/{sample_project['id']}",
        headers={"X-ReleaseGuard-Token": "shared-secret"},
    )

    assert response.status_code == 200, response.text
