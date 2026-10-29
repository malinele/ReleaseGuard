"""Rate limiting tests for server-rendered UI login attempts."""

import re

import pytest

from app.auth import USER_AUTH_ENV
from app.services.user_service import UserService
from app.ui import routes as ui_routes


CSRF_INPUT_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture(autouse=True)
def _clean_auth_env_and_rate_limit(monkeypatch):
    """Start each test with auth env controls disabled and limiter reset."""
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)
    ui_routes._LOGIN_RATE_LIMIT.clear()


def _csrf_token_from(html: str) -> str:
    match = CSRF_INPUT_RE.search(html)
    assert match is not None, html
    return match.group(1)


def _create_user(db_session, username="ui-user"):
    return UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
    )


def _post_login(client, *, username="ui-user", password="wrong-password"):
    page = client.get("/login")
    return client.post(
        "/login",
        data={
            "username": username,
            "password": password,
            "csrf_token": _csrf_token_from(page.text),
        },
        follow_redirects=False,
    )


def test_repeated_failed_login_attempts_are_rate_limited(
    client,
    db_session,
    monkeypatch,
):
    """Repeated bad credentials from same client and username should return 429."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    _create_user(db_session)

    for _ in range(ui_routes.LOGIN_RATE_LIMIT_MAX_FAILURES):
        response = _post_login(client)
        assert response.status_code == 401, response.text

    limited = _post_login(client)

    assert limited.status_code == 429, limited.text
    assert "Too many login attempts" in limited.text


def test_login_rate_limit_is_scoped_by_username(client, db_session, monkeypatch):
    """Locking one username must not block another username."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    _create_user(db_session, username="ui-user")
    _create_user(db_session, username="other-user")

    for _ in range(ui_routes.LOGIN_RATE_LIMIT_MAX_FAILURES + 1):
        _post_login(client, username="ui-user")

    response = _post_login(
        client,
        username="other-user",
        password="correct-password",
    )

    assert response.status_code == 303, response.text


def test_successful_login_resets_rate_limit(client, db_session, monkeypatch):
    """A successful login should clear previous failures for that username."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    _create_user(db_session)

    for _ in range(ui_routes.LOGIN_RATE_LIMIT_MAX_FAILURES - 1):
        response = _post_login(client)
        assert response.status_code == 401, response.text

    success = _post_login(client, password="correct-password")
    assert success.status_code == 303, success.text

    after_success = _post_login(client)
    assert after_success.status_code == 401, after_success.text
