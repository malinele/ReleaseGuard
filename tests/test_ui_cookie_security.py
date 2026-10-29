"""UI cookie security tests."""

import re

import pytest

from app.auth import RELEASEGUARD_ENV, USER_AUTH_ENV
from app.services.user_service import UserService
from app.ui.routes import UI_CSRF_COOKIE, UI_SESSION_COOKIE


CSRF_INPUT_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Start each test with auth env controls disabled."""
    monkeypatch.delenv(RELEASEGUARD_ENV, raising=False)
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)


def _csrf_token_from(html: str) -> str:
    match = CSRF_INPUT_RE.search(html)
    assert match is not None, html
    return match.group(1)


def _create_user(db_session):
    return UserService.create_user(
        db_session,
        username="cookie-user",
        password="correct-password",
    )


def _login(client, *, base_url: str = ""):
    login_page = client.get(f"{base_url}/login")
    return client.post(
        f"{base_url}/login",
        data={
            "username": "cookie-user",
            "password": "correct-password",
            "csrf_token": _csrf_token_from(login_page.text),
        },
        follow_redirects=False,
    )


def _set_cookie_headers(response):
    return response.headers.get_list("set-cookie")


def _cookie_header(response, cookie_name: str) -> str:
    for header in _set_cookie_headers(response):
        if header.startswith(f"{cookie_name}="):
            return header
    raise AssertionError(f"missing Set-Cookie header for {cookie_name}")


def test_local_dev_ui_cookies_are_not_forced_secure(client, db_session):
    """Local HTTP development should keep cookies usable without Secure."""
    _create_user(db_session)

    login_response = _login(client)

    assert login_response.status_code == 303, login_response.text
    assert "secure" not in _cookie_header(login_response, UI_SESSION_COOKIE).lower()
    assert "secure" not in _cookie_header(login_response, UI_CSRF_COOKIE).lower()


@pytest.mark.parametrize("value", ["production", "prod"])
def test_production_login_sets_secure_session_and_csrf_cookies(
    client,
    db_session,
    monkeypatch,
    value,
):
    """Production UI login cookies must use the Secure attribute."""
    _create_user(db_session)
    monkeypatch.setenv(RELEASEGUARD_ENV, value)

    login_response = _login(client, base_url="https://testserver")

    assert login_response.status_code == 303, login_response.text
    assert "secure" in _cookie_header(login_response, UI_SESSION_COOKIE).lower()
    assert "secure" in _cookie_header(login_response, UI_CSRF_COOKIE).lower()


def test_production_login_form_sets_secure_csrf_cookie(client, monkeypatch):
    """Production login forms should also emit Secure CSRF cookies."""
    monkeypatch.setenv(RELEASEGUARD_ENV, "production")

    response = client.get("/login")

    assert response.status_code == 200, response.text
    assert "secure" in _cookie_header(response, UI_CSRF_COOKIE).lower()
