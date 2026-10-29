"""RBAC enforcement tests for requirement write endpoints."""
import uuid

import pytest

from app.auth import USER_AUTH_ENV, WRITE_TOKEN_ENV
from app.rbac import ROLE_ADMIN, ROLE_FINANCE, ROLE_OWNER, ROLE_SUPPORT, ROLE_VIEWER
from app.services.session_service import SessionService
from app.services.user_service import UserService


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Start each test with auth env controls disabled."""
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)
    monkeypatch.delenv(WRITE_TOKEN_ENV, raising=False)


def _create_user_token(db_session, *, role):
    # Per-call unique username so the helper can run across multiple tests
    # and pytest invocations against the shared SQLite DB without colliding
    # on the unique username/email. UserService.create_user commits, so
    # without uniqueness stale rows would survive across tests in the same
    # session and break the users fixture on subsequent invocations.
    username = f"{role}-requirement-user-{uuid.uuid4().hex[:8]}"
    user = UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


def _requirement_create_payload(sample_project, requirement_id):
    return {
        "project_id": sample_project["id"],
        "requirement_id": requirement_id,
        "title": "RBAC requirement",
        "description": "Requirement created by RBAC test.",
        "priority": "medium",
        "status": "active",
    }


def _requirement_update_payload():
    return {
        "title": "Updated by RBAC test",
        "priority": "high",
    }


@pytest.mark.parametrize("allowed_role", [ROLE_OWNER, ROLE_ADMIN, ROLE_SUPPORT])
def test_create_requirement_allows_policy_roles(client, db_session, sample_project, monkeypatch, allowed_role):
    """owner/admin/support bearer sessions can create requirements when auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=allowed_role)

    response = client.post(
        "/api/requirements",
        json=_requirement_create_payload(
            sample_project,
            requirement_id=f"REQ-{allowed_role.upper()}-{uuid.uuid4().hex[:8]}",
        ),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text


@pytest.mark.parametrize("denied_role", [ROLE_FINANCE, ROLE_VIEWER])
def test_create_requirement_denies_non_writer_roles(client, db_session, sample_project, monkeypatch, denied_role):
    """finance/viewer bearer sessions are authenticated but not authorized."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=denied_role)

    response = client.post(
        "/api/requirements",
        json=_requirement_create_payload(
            sample_project,
            requirement_id=f"REQ-{denied_role.upper()}-{uuid.uuid4().hex[:8]}",
        ),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403, response.text


def test_create_requirement_requires_bearer_when_user_auth_enabled(client, sample_project, monkeypatch):
    """Missing bearer session returns 401 when user auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.post(
        "/api/requirements",
        json=_requirement_create_payload(sample_project, f"REQ-MISSING-{uuid.uuid4().hex[:8]}"),
    )

    assert response.status_code == 401, response.text


def test_create_requirement_rejects_invalid_bearer(client, sample_project, monkeypatch):
    """Invalid bearer token returns 401 when user auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.post(
        "/api/requirements",
        json=_requirement_create_payload(sample_project, f"REQ-INVALID-{uuid.uuid4().hex[:8]}"),
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401, response.text


def test_create_requirement_preserves_shared_token_compatibility(client, sample_project, monkeypatch):
    """A valid shared token still authorizes requirement writes."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = client.post(
        "/api/requirements",
        json=_requirement_create_payload(sample_project, f"REQ-TOKEN-{uuid.uuid4().hex[:8]}"),
        headers={"X-ReleaseGuard-Token": "shared-secret"},
    )

    assert response.status_code == 201, response.text


def test_update_requirement_requires_writer_role(client, db_session, sample_requirement, monkeypatch):
    """PUT /api/requirements/{id} enforces requirements:write."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    denied_token = _create_user_token(db_session, role=ROLE_VIEWER)
    allowed_token = _create_user_token(db_session, role=ROLE_SUPPORT)

    denied = client.put(
        f"/api/requirements/{sample_requirement['id']}",
        json=_requirement_update_payload(),
        headers={"Authorization": f"Bearer {denied_token}"},
    )
    allowed = client.put(
        f"/api/requirements/{sample_requirement['id']}",
        json=_requirement_update_payload(),
        headers={"Authorization": f"Bearer {allowed_token}"},
    )

    assert denied.status_code == 403, denied.text
    assert allowed.status_code == 200, allowed.text


def test_delete_requirement_requires_writer_role(client, db_session, sample_requirement, monkeypatch):
    """DELETE /api/requirements/{id} enforces requirements:write."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    denied_token = _create_user_token(db_session, role=ROLE_FINANCE)
    allowed_token = _create_user_token(db_session, role=ROLE_ADMIN)

    denied = client.delete(
        f"/api/requirements/{sample_requirement['id']}",
        headers={"Authorization": f"Bearer {denied_token}"},
    )
    allowed = client.delete(
        f"/api/requirements/{sample_requirement['id']}",
        headers={"Authorization": f"Bearer {allowed_token}"},
    )

    assert denied.status_code == 403, denied.text
    assert allowed.status_code == 204, allowed.text


def test_get_requirements_not_gated_by_requirements_write_slice(client, db_session, monkeypatch):
    """GET requirements remains a read path and is not subject to requirements:write."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=ROLE_VIEWER)

    response = client.get(
        "/api/requirements",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def test_create_requirement_local_dev_behavior_when_user_auth_unset(client, sample_project):
    """When user auth is not required, requirement creation keeps existing local-dev behavior."""
    response = client.post(
        "/api/requirements",
        json=_requirement_create_payload(
            sample_project,
            requirement_id=f"REQ-LOCAL-{uuid.uuid4().hex[:8]}",
        ),
    )

    assert response.status_code == 201, response.text
