"""Admin password reset tests for local users."""

import re
import uuid

import pytest

from app.auth import USER_AUTH_ENV
from app.models.audit_event import AuditAction, AuditEvent
from app.rbac import ROLE_ADMIN, ROLE_VIEWER
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


def _create_user(db_session, *, role=ROLE_ADMIN, username=None):
    username = username or f"{role}-password-reset-{uuid.uuid4().hex[:8]}"
    return UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
        role=role,
    )


def _session_token(db_session, user):
    return SessionService.create_session(db_session, user_id=user.id).token


def _lock_user(db_session, user):
    for _ in range(UserService.MAX_FAILED_LOGIN_ATTEMPTS):
        UserService.record_failed_login(db_session, user)
    db_session.refresh(user)
    assert UserService.user_is_locked(user) is True


def _audit_events(db_session):
    return db_session.query(AuditEvent).order_by(AuditEvent.id.asc()).all()


def test_admin_users_page_shows_password_reset_form(client, db_session, monkeypatch):
    """Admin users should have an explicit password reset form for local users."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    admin = _create_user(db_session, role=ROLE_ADMIN)
    target = _create_user(db_session, username="reset-target")
    token = _session_token(db_session, admin)

    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert f"/admin/users/{target.id}/password" in response.text
    assert "Reset password" in response.text
    assert "correct-password" not in response.text


def test_admin_can_reset_password_and_clear_lockout(client, db_session, monkeypatch):
    """Admin password reset should rotate the hash and clear lockout state."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    admin = _create_user(db_session, role=ROLE_ADMIN)
    target = _create_user(db_session, username="reset-target")
    _lock_user(db_session, target)
    old_hash = target.password_hash
    token = _session_token(db_session, admin)
    page = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.post(
        f"/admin/users/{target.id}/password",
        data={
            "new_password": "new-correct-password",
            "csrf_token": _csrf_token_from(page.text),
        },
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=False,
    )

    db_session.refresh(target)
    assert response.status_code == 303, response.text
    assert target.password_hash != old_hash
    assert target.failed_login_attempts == 0
    assert target.locked_until is None
    assert UserService.verify_user_password(
        db_session, "reset-target", "correct-password"
    ) is False
    assert UserService.verify_user_password(
        db_session, "reset-target", "new-correct-password"
    ) is True


def test_admin_password_reset_records_audit_without_secret(
    client,
    db_session,
    monkeypatch,
):
    """Password reset audit output must not contain submitted credentials."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    admin = _create_user(db_session, role=ROLE_ADMIN, username="admin-user")
    target = _create_user(db_session, username="reset-target")
    token = _session_token(db_session, admin)
    page = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.post(
        f"/admin/users/{target.id}/password",
        data={
            "new_password": "new-correct-password",
            "csrf_token": _csrf_token_from(page.text),
        },
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=False,
    )
    events = _audit_events(db_session)

    assert response.status_code == 303, response.text
    assert len(events) == 1
    event = events[0]
    assert event.actor == "admin-user"
    assert event.action == AuditAction.UPDATE
    assert event.entity_type == "user"
    assert event.entity_id == target.id
    assert event.after_summary == "ui_user_password_reset username=reset-target"
    assert "new-correct-password" not in (event.after_summary or "")


def test_viewer_cannot_reset_password(client, db_session, monkeypatch):
    """Non-admin users cannot reset another user's password."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    viewer = _create_user(db_session, role=ROLE_VIEWER)
    target = _create_user(db_session, username="reset-target")
    old_hash = target.password_hash
    token = _session_token(db_session, viewer)
    page = client.get(
        "/login",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.post(
        f"/admin/users/{target.id}/password",
        data={
            "new_password": "new-correct-password",
            "csrf_token": _csrf_token_from(page.text),
        },
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=False,
    )

    db_session.refresh(target)
    assert response.status_code == 403, response.text
    assert target.password_hash == old_hash
