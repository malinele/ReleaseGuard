"""RBAC enforcement tests for project write endpoints."""
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
    username = f"{role}-project-user-{uuid.uuid4().hex[:8]}"
    user = UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


def _project_create_payload(name_prefix="RBAC Project"):
    return {
        "name": f"{name_prefix} {uuid.uuid4().hex[:8]}",
        "description": "Project created by RBAC test.",
    }


def _project_update_payload():
    return {
        "name": f"Updated RBAC Project {uuid.uuid4().hex[:8]}",
        "description": "Updated by RBAC test.",
    }


def _create_project(client):
    response = client.post("/api/projects", json=_project_create_payload("Fixture Project"))
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("allowed_role", [ROLE_OWNER, ROLE_ADMIN, ROLE_SUPPORT])
def test_create_project_allows_policy_roles(client, db_session, monkeypatch, allowed_role):
    """owner/admin/support bearer sessions can create projects when auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=allowed_role)

    response = client.post(
        "/api/projects",
        json=_project_create_payload(f"Project {allowed_role}"),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text


@pytest.mark.parametrize("denied_role", [ROLE_FINANCE, ROLE_VIEWER])
def test_create_project_denies_non_writer_roles(client, db_session, monkeypatch, denied_role):
    """finance/viewer bearer sessions are authenticated but not authorized."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=denied_role)

    response = client.post(
        "/api/projects",
        json=_project_create_payload(f"Project {denied_role}"),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403, response.text


def test_create_project_requires_bearer_when_user_auth_enabled(client, monkeypatch):
    """Missing bearer session returns 401 when user auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.post("/api/projects", json=_project_create_payload())

    assert response.status_code == 401, response.text


def test_create_project_rejects_invalid_bearer(client, monkeypatch):
    """Invalid bearer token returns 401 when user auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.post(
        "/api/projects",
        json=_project_create_payload(),
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401, response.text


def test_create_project_preserves_shared_token_compatibility(client, monkeypatch):
    """A valid shared token still authorizes project writes."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = client.post(
        "/api/projects",
        json=_project_create_payload(),
        headers={"X-ReleaseGuard-Token": "shared-secret"},
    )

    assert response.status_code == 201, response.text


def test_update_project_requires_writer_role(client, db_session, monkeypatch):
    """PUT /api/projects/{id} enforces projects:write."""
    project = _create_project(client)
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    denied_token = _create_user_token(db_session, role=ROLE_VIEWER)
    allowed_token = _create_user_token(db_session, role=ROLE_SUPPORT)

    denied = client.put(
        f"/api/projects/{project['id']}",
        json=_project_update_payload(),
        headers={"Authorization": f"Bearer {denied_token}"},
    )
    allowed = client.put(
        f"/api/projects/{project['id']}",
        json=_project_update_payload(),
        headers={"Authorization": f"Bearer {allowed_token}"},
    )

    assert denied.status_code == 403, denied.text
    assert allowed.status_code == 200, allowed.text


def test_delete_project_requires_writer_role(client, db_session, monkeypatch):
    """DELETE /api/projects/{id} enforces projects:write."""
    project = _create_project(client)
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    denied_token = _create_user_token(db_session, role=ROLE_FINANCE)
    allowed_token = _create_user_token(db_session, role=ROLE_ADMIN)

    denied = client.delete(
        f"/api/projects/{project['id']}",
        headers={"Authorization": f"Bearer {denied_token}"},
    )
    allowed = client.delete(
        f"/api/projects/{project['id']}",
        headers={"Authorization": f"Bearer {allowed_token}"},
    )

    assert denied.status_code == 403, denied.text
    assert allowed.status_code == 204, allowed.text


def test_get_projects_not_gated_by_projects_write_slice(client, db_session, monkeypatch):
    """GET projects remains a read path and is not subject to projects:write."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=ROLE_VIEWER)

    response = client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def test_create_project_local_dev_behavior_when_user_auth_unset(client):
    """When user auth is not required, project creation keeps existing local-dev behavior."""
    response = client.post("/api/projects", json=_project_create_payload())

    assert response.status_code == 201, response.text
