"""Account lockout tests for local users."""

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


def _create_user(db_session, username="locked-user"):
    return UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
    )


def _post_login(client, *, username="locked-user", password="wrong-password"):
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


def test_user_service_locks_user_after_failed_attempt_threshold(db_session):
    """Repeated failed credential checks persistently lock the local account."""
    user = _create_user(db_session)

    for _ in range(UserService.MAX_FAILED_LOGIN_ATTEMPTS):
        UserService.record_failed_login(db_session, user)

    db_session.refresh(user)
    assert user.failed_login_attempts == UserService.MAX_FAILED_LOGIN_ATTEMPTS
    assert user.locked_until is not None
    assert UserService.user_is_locked(user) is True


def test_successful_password_verification_clears_previous_failures(db_session):
    """A valid password clears non-locking failed attempts."""
    user = _create_user(db_session)
    UserService.record_failed_login(db_session, user)
    UserService.record_failed_login(db_session, user)

    assert UserService.verify_user_password(db_session, "locked-user", "correct-password") is True

    db_session.refresh(user)
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


def test_locked_user_password_verification_fails_even_with_correct_password(db_session):
    """Locked users cannot authenticate until lockout expires."""
    user = _create_user(db_session)
    for _ in range(UserService.MAX_FAILED_LOGIN_ATTEMPTS):
        UserService.record_failed_login(db_session, user)

    assert UserService.verify_user_password(db_session, "locked-user", "correct-password") is False


def test_ui_login_locks_account_after_failed_attempts(client, db_session, monkeypatch):
    """UI login should lock the account after repeated bad credentials."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    user = _create_user(db_session)

    for _ in range(UserService.MAX_FAILED_LOGIN_ATTEMPTS):
        response = _post_login(client)
        assert response.status_code == 401, response.text

    db_session.refresh(user)
    assert UserService.user_is_locked(user) is True


def test_ui_login_reports_locked_account_after_rate_limit_reset(
    client,
    db_session,
    monkeypatch,
):
    """Persistent account lockout should survive the in-process rate limiter."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    _create_user(db_session)
    for _ in range(UserService.MAX_FAILED_LOGIN_ATTEMPTS):
        _post_login(client)

    ui_routes._LOGIN_RATE_LIMIT.clear()
    response = _post_login(client, password="correct-password")

    assert response.status_code == 423, response.text
    assert "Account locked" in response.text
