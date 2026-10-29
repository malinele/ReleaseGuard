"""Role-aware authorization tests for server-rendered UI routes."""

import uuid

import pytest

from app.auth import USER_AUTH_ENV, WRITE_TOKEN_ENV
from app.rbac import ROLE_FINANCE, ROLE_SUPPORT, ROLE_VIEWER
from app.services.session_service import SessionService
from app.services.user_service import UserService


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Start each test with auth env controls disabled."""
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)
    monkeypatch.delenv(WRITE_TOKEN_ENV, raising=False)


def _create_user_token(db_session, *, role):
    username = f"{role}-ui-rbac-user-{uuid.uuid4().hex[:8]}"
    user = UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


@pytest.mark.parametrize("endpoint", ["/audit", "/traceability"])
def test_viewer_is_denied_role_restricted_ui_pages(
    client,
    db_session,
    monkeypatch,
    endpoint,
):
    """Viewer sessions authenticate but cannot access restricted UI pages."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=ROLE_VIEWER)

    response = client.get(endpoint, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403, response.text


def test_finance_can_access_audit_ui(client, db_session, monkeypatch):
    """Finance users can access the audit UI through the existing audit:read policy."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=ROLE_FINANCE)

    response = client.get("/audit", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text


def test_support_can_access_traceability_ui(client, db_session, monkeypatch):
    """Support users can access traceability UI through traceability:read."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=ROLE_SUPPORT)

    response = client.get("/traceability", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text


def test_shared_token_still_bypasses_ui_role_checks(client, monkeypatch):
    """The shared token remains a compatibility override for automation."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = client.get(
        "/audit",
        headers={"X-ReleaseGuard-Token": "shared-secret"},
    )

    assert response.status_code == 200, response.text


def test_local_dev_keeps_restricted_ui_pages_open_when_auth_unset(client):
    """Role checks are not applied when user auth is not required."""
    response = client.get("/traceability")

    assert response.status_code == 200, response.text
