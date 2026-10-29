"""Authentication tests for server-rendered UI routes."""
import uuid

import pytest

from app.auth import USER_AUTH_ENV, WRITE_TOKEN_ENV
from app.rbac import ROLE_FINANCE
from app.services.session_service import SessionService
from app.services.user_service import UserService


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Start each test with auth env controls disabled."""
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)
    monkeypatch.delenv(WRITE_TOKEN_ENV, raising=False)


def _create_user_token(db_session, *, role=ROLE_FINANCE):
    username = f"{role}-ui-user-{uuid.uuid4().hex[:8]}"
    user = UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


def _ui_endpoints(sample_project, sample_requirement, sample_proposal):
    return [
        "/",
        "/projects",
        f"/projects/{sample_project['id']}",
        "/evidence",
        "/requirements",
        f"/requirements/{sample_requirement['id']}",
        f"/proposals/{sample_proposal['id']}",
        "/traceability",
        "/audit",
    ]


def test_ui_routes_require_bearer_when_user_auth_enabled(
    client,
    sample_project,
    sample_requirement,
    sample_proposal,
    monkeypatch,
):
    """UI routes return 401 without a bearer session when user auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    for endpoint in _ui_endpoints(sample_project, sample_requirement, sample_proposal):
        response = client.get(endpoint)

        assert response.status_code == 401, endpoint


def test_ui_routes_allow_valid_bearer_session(
    client,
    db_session,
    sample_project,
    sample_requirement,
    sample_proposal,
    monkeypatch,
):
    """A valid role-authorized bearer session can access readonly UI pages."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session)

    for endpoint in _ui_endpoints(sample_project, sample_requirement, sample_proposal):
        response = client.get(endpoint, headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200, endpoint


def test_ui_routes_reject_invalid_bearer(client, monkeypatch):
    """Invalid bearer token returns 401 before route-specific database lookups."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.get(
        "/projects/999999",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401, response.text


def test_ui_routes_preserve_shared_token_compatibility(client, sample_project, monkeypatch):
    """A valid shared token still authorizes UI route access for automation."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = client.get(
        f"/projects/{sample_project['id']}",
        headers={"X-ReleaseGuard-Token": "shared-secret"},
    )

    assert response.status_code == 200, response.text


def test_ui_routes_local_dev_behavior_when_user_auth_unset(client, sample_project):
    """When user auth is not required, UI routes keep existing local-dev behavior."""
    response = client.get(f"/projects/{sample_project['id']}")

    assert response.status_code == 200, response.text
