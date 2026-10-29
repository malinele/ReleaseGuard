"""Audit event coverage for server-rendered auth and user-management UI."""

import re
import uuid

import pytest

from app.auth import USER_AUTH_ENV
from app.models.audit_event import AuditAction, AuditEvent
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


def _create_user(db_session, *, username="ui-user", role=ROLE_ADMIN):
    return UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
        role=role,
    )


def _login(client, *, username="ui-user", password="correct-password"):
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


def _audit_events(db_session):
    return db_session.query(AuditEvent).order_by(AuditEvent.id.asc()).all()


def test_successful_ui_login_creates_audit_event(client, db_session, monkeypatch):
    """Successful login should be visible in audit history without secrets."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    user = _create_user(db_session)

    response = _login(client)
    events = _audit_events(db_session)

    assert response.status_code == 303, response.text
    assert len(events) == 1
    event = events[0]
    assert event.actor == user.username
    assert event.action == AuditAction.CREATE
    assert event.entity_type == "user_session"
    assert event.entity_id == user.id
    assert event.after_summary == "ui_login_success"
    assert "correct-password" not in (event.before_summary or "")
    assert "correct-password" not in (event.after_summary or "")


def test_failed_ui_login_creates_audit_event_without_password(
    client,
    db_session,
    monkeypatch,
):
    """Failed login attempts should be auditable without storing credentials."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    _create_user(db_session)

    response = _login(client, password="wrong-password")
    events = _audit_events(db_session)

    assert response.status_code == 401, response.text
    assert len(events) == 1
    event = events[0]
    assert event.actor == "ui-user"
    assert event.action == AuditAction.CREATE
    assert event.entity_type == "user_session"
    assert event.entity_id is None
    assert event.after_summary == "ui_login_failed"
    assert "wrong-password" not in (event.before_summary or "")
    assert "wrong-password" not in (event.after_summary or "")


def test_ui_logout_creates_audit_event(client, db_session, monkeypatch):
    """Logout should record the user whose session was revoked."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    user = _create_user(db_session)
    assert _login(client).status_code == 303
    page = client.get("/")

    response = client.post(
        "/logout",
        data={"csrf_token": _csrf_token_from(page.text)},
        follow_redirects=False,
    )
    events = _audit_events(db_session)

    assert response.status_code == 303, response.text
    assert [event.after_summary for event in events] == [
        "ui_login_success",
        "ui_logout",
    ]
    assert events[-1].actor == user.username
    assert events[-1].action == AuditAction.UPDATE
    assert events[-1].entity_type == "user_session"
    assert events[-1].entity_id == user.id


def test_admin_user_create_creates_audit_event(client, db_session, monkeypatch):
    """Creating a local user through the admin UI should be audited."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    admin = _create_user(
        db_session,
        username=f"admin-{uuid.uuid4().hex[:8]}",
    )
    session_token = SessionService.create_session(db_session, user_id=admin.id).token
    page = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {session_token}"},
    )

    response = client.post(
        "/admin/users",
        data={
            "username": "managed-user",
            "password": "managed-password",
            "display_name": "Managed User",
            "role": "viewer",
            "csrf_token": _csrf_token_from(page.text),
        },
        headers={"Authorization": f"Bearer {session_token}"},
        follow_redirects=False,
    )
    created = UserService.get_user_by_username(db_session, "managed-user")
    events = _audit_events(db_session)

    assert response.status_code == 303, response.text
    assert created is not None
    assert len(events) == 1
    event = events[0]
    assert event.actor == admin.username
    assert event.action == AuditAction.CREATE
    assert event.entity_type == "user"
    assert event.entity_id == created.id
    assert event.after_summary == "ui_user_created username=managed-user role=viewer"
    assert "managed-password" not in (event.before_summary or "")
    assert "managed-password" not in (event.after_summary or "")
