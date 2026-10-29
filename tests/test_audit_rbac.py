"""RBAC enforcement tests for audit read endpoints."""
import uuid

import pytest

from app.auth import USER_AUTH_ENV, WRITE_TOKEN_ENV
from app.models.audit_event import AuditAction
from app.rbac import ROLE_ADMIN, ROLE_FINANCE, ROLE_OWNER, ROLE_SUPPORT, ROLE_VIEWER
from app.services.audit_service import AuditService
from app.services.session_service import SessionService
from app.services.user_service import UserService


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Start each test with auth env controls disabled."""
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)
    monkeypatch.delenv(WRITE_TOKEN_ENV, raising=False)


def _create_user_token(db_session, *, role):
    username = f"{role}-audit-user-{uuid.uuid4().hex[:8]}"
    user = UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


def _create_audit_event(db_session):
    return AuditService.create_audit_event(
        db_session,
        actor="audit-rbac-test",
        action=AuditAction.CREATE,
        entity_type="project",
        entity_id=1,
        after_summary="audit rbac test event",
    )


@pytest.mark.parametrize("endpoint", ["/api/audit", "/api/audit/export"])
@pytest.mark.parametrize("allowed_role", [ROLE_OWNER, ROLE_ADMIN, ROLE_FINANCE])
def test_audit_collection_endpoints_allow_policy_roles(client, db_session, monkeypatch, endpoint, allowed_role):
    """owner/admin/finance bearer sessions can read audit collection/export."""
    _create_audit_event(db_session)
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=allowed_role)

    response = client.get(endpoint, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text


@pytest.mark.parametrize("endpoint", ["/api/audit", "/api/audit/export"])
@pytest.mark.parametrize("denied_role", [ROLE_SUPPORT, ROLE_VIEWER])
def test_audit_collection_endpoints_deny_non_reader_roles(client, db_session, monkeypatch, endpoint, denied_role):
    """support/viewer bearer sessions are authenticated but not authorized for audit:read."""
    _create_audit_event(db_session)
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=denied_role)

    response = client.get(endpoint, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403, response.text


def test_audit_detail_allows_finance_and_denies_viewer(client, db_session, monkeypatch):
    """GET /api/audit/{id} enforces audit:read."""
    event = _create_audit_event(db_session)
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    finance_token = _create_user_token(db_session, role=ROLE_FINANCE)
    viewer_token = _create_user_token(db_session, role=ROLE_VIEWER)

    allowed = client.get(
        f"/api/audit/{event.id}",
        headers={"Authorization": f"Bearer {finance_token}"},
    )
    denied = client.get(
        f"/api/audit/{event.id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert allowed.status_code == 200, allowed.text
    assert denied.status_code == 403, denied.text


def test_audit_read_requires_bearer_when_user_auth_enabled(client, db_session, monkeypatch):
    """Missing bearer session returns 401 when user auth is enabled."""
    _create_audit_event(db_session)
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.get("/api/audit")

    assert response.status_code == 401, response.text


def test_audit_read_rejects_invalid_bearer(client, db_session, monkeypatch):
    """Invalid bearer token returns 401 when user auth is enabled."""
    _create_audit_event(db_session)
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.get(
        "/api/audit",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401, response.text


def test_audit_read_preserves_shared_token_compatibility(client, db_session, monkeypatch):
    """A valid shared token still authorizes audit reads."""
    _create_audit_event(db_session)
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = client.get(
        "/api/audit",
        headers={"X-ReleaseGuard-Token": "shared-secret"},
    )

    assert response.status_code == 200, response.text


def test_audit_read_local_dev_behavior_when_user_auth_unset(client, db_session):
    """When user auth is not required, audit reads keep existing local-dev behavior."""
    _create_audit_event(db_session)

    response = client.get("/api/audit")

    assert response.status_code == 200, response.text
