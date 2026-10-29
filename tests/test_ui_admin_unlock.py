"""Admin unlock tests for locked local users."""

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
    username = username or f"{role}-unlock-{uuid.uuid4().hex[:8]}"
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


def test_admin_users_page_shows_unlock_action_for_locked_user(
    client,
    db_session,
    monkeypatch,
):
    """Locked users should have an explicit admin unlock form."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    admin = _create_user(db_session, role=ROLE_ADMIN)
    locked = _create_user(db_session, username="locked-user")
    _lock_user(db_session, locked)
    token = _session_token(db_session, admin)

    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert f"/admin/users/{locked.id}/unlock" in response.text
    assert "Unlock" in response.text


def test_admin_can_unlock_locked_user(client, db_session, monkeypatch):
    """Admin unlock clears failed attempts and locked_until."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    admin = _create_user(db_session, role=ROLE_ADMIN)
    locked = _create_user(db_session, username="locked-user")
    _lock_user(db_session, locked)
    token = _session_token(db_session, admin)
    page = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.post(
        f"/admin/users/{locked.id}/unlock",
        data={"csrf_token": _csrf_token_from(page.text)},
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=False,
    )

    db_session.refresh(locked)
    assert response.status_code == 303, response.text
    assert locked.failed_login_attempts == 0
    assert locked.locked_until is None
    assert UserService.user_is_locked(locked) is False


def test_admin_unlock_records_audit_event(client, db_session, monkeypatch):
    """Unlocking a user should leave an audit trail without secrets."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    admin = _create_user(db_session, role=ROLE_ADMIN, username="admin-user")
    locked = _create_user(db_session, username="locked-user")
    _lock_user(db_session, locked)
    token = _session_token(db_session, admin)
    page = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.post(
        f"/admin/users/{locked.id}/unlock",
        data={"csrf_token": _csrf_token_from(page.text)},
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
    assert event.entity_id == locked.id
    assert event.after_summary == "ui_user_unlocked username=locked-user"


def test_viewer_cannot_unlock_locked_user(client, db_session, monkeypatch):
    """Non-admin users cannot unlock accounts."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    viewer = _create_user(db_session, role=ROLE_VIEWER)
    locked = _create_user(db_session, username="locked-user")
    _lock_user(db_session, locked)
    token = _session_token(db_session, viewer)
    page = client.get(
        "/login",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.post(
        f"/admin/users/{locked.id}/unlock",
        data={"csrf_token": _csrf_token_from(page.text)},
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=False,
    )

    db_session.refresh(locked)
    assert response.status_code == 403, response.text
    assert UserService.user_is_locked(locked) is True
