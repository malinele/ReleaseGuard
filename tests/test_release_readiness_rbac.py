"""RBAC enforcement tests for release readiness read endpoint."""
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
    username = f"{role}-release-readiness-user-{uuid.uuid4().hex[:8]}"
    user = UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


@pytest.mark.parametrize(
    "allowed_role",
    [ROLE_OWNER, ROLE_ADMIN, ROLE_FINANCE, ROLE_SUPPORT, ROLE_VIEWER],
)
def test_release_readiness_allows_policy_roles(client, db_session, sample_proposal, monkeypatch, allowed_role):
    """All policy roles can read release readiness."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=allowed_role)

    response = client.get(
        "/api/release-readiness",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) == {"total_proposals", "release_ready", "blocked", "items"}


def test_release_readiness_requires_bearer_when_user_auth_enabled(client, monkeypatch):
    """Missing bearer session returns 401 when user auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.get("/api/release-readiness")

    assert response.status_code == 401, response.text


def test_release_readiness_rejects_invalid_bearer(client, monkeypatch):
    """Invalid bearer token returns 401 when user auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.get(
        "/api/release-readiness",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401, response.text


def test_release_readiness_preserves_shared_token_compatibility(client, sample_proposal, monkeypatch):
    """A valid shared token still authorizes release readiness reads."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = client.get(
        "/api/release-readiness",
        headers={"X-ReleaseGuard-Token": "shared-secret"},
    )

    assert response.status_code == 200, response.text


def test_release_readiness_local_dev_behavior_when_user_auth_unset(client, sample_proposal):
    """When user auth is not required, release readiness keeps existing local-dev behavior."""
    response = client.get("/api/release-readiness")

    assert response.status_code == 200, response.text
