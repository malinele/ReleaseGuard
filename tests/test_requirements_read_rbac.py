"""RBAC enforcement tests for requirement read endpoints."""
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
    username = f"{role}-requirement-read-user-{uuid.uuid4().hex[:8]}"
    user = UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


def _requirement_read_endpoints(sample_requirement):
    return [
        "/api/requirements",
        f"/api/requirements/{sample_requirement['id']}",
    ]


@pytest.mark.parametrize(
    "allowed_role",
    [ROLE_OWNER, ROLE_ADMIN, ROLE_FINANCE, ROLE_SUPPORT, ROLE_VIEWER],
)
def test_requirement_read_allows_policy_roles(client, db_session, sample_requirement, monkeypatch, allowed_role):
    """All policy roles can read requirement collection and detail endpoints."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=allowed_role)

    for endpoint in _requirement_read_endpoints(sample_requirement):
        response = client.get(endpoint, headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200, response.text


@pytest.mark.parametrize("endpoint", ["/api/requirements", "/api/requirements/1"])
def test_requirement_read_requires_bearer_when_user_auth_enabled(client, monkeypatch, endpoint):
    """Missing bearer session returns 401 when user auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.get(endpoint)

    assert response.status_code == 401, response.text


def test_requirement_read_rejects_invalid_bearer(client, monkeypatch):
    """Invalid bearer token returns 401 when user auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.get(
        "/api/requirements",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401, response.text


def test_requirement_read_preserves_shared_token_compatibility(client, sample_requirement, monkeypatch):
    """A valid shared token still authorizes requirement reads."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    for endpoint in _requirement_read_endpoints(sample_requirement):
        response = client.get(
            endpoint,
            headers={"X-ReleaseGuard-Token": "shared-secret"},
        )

        assert response.status_code == 200, response.text


def test_requirement_read_local_dev_behavior_when_user_auth_unset(client, sample_requirement):
    """When user auth is not required, requirement reads keep existing local-dev behavior."""
    for endpoint in _requirement_read_endpoints(sample_requirement):
        response = client.get(endpoint)

        assert response.status_code == 200, response.text


def test_requirement_missing_detail_still_requires_allowed_role(client, db_session, monkeypatch):
    """An allowed role reaches normal 404 handling after auth passes."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=ROLE_VIEWER)

    response = client.get(
        "/api/requirements/999999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404, response.text
