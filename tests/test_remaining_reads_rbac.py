"""RBAC enforcement tests for the remaining proposal-scoped GET routes."""
import uuid

import pytest

from app.auth import USER_AUTH_ENV, WRITE_TOKEN_ENV
from app.rbac import (
    ROLE_ADMIN,
    ROLE_FINANCE,
    ROLE_OWNER,
    ROLE_SUPPORT,
    ROLE_VIEWER,
    is_role_allowed,
)
from app.services.session_service import SessionService
from app.services.user_service import UserService

ALL_ROLES = [ROLE_OWNER, ROLE_ADMIN, ROLE_FINANCE, ROLE_SUPPORT, ROLE_VIEWER]

# action -> (url suffix, status returned once the gate passes for an empty proposal)
READ_ROUTES = {
    "proposal_requirements:read": ("requirements", 200),
    "test_evidence:read": ("test-evidence", 200),
    "security_reviews:read": ("security-review", 404),
    "release_decisions:read": ("release-decision", 404),
}
ACTIONS = list(READ_ROUTES)


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Start each test with auth env controls disabled."""
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)
    monkeypatch.delenv(WRITE_TOKEN_ENV, raising=False)


def _create_user_token(db_session, *, role):
    user = UserService.create_user(
        db_session,
        username=f"{role}-remainingread-user-{uuid.uuid4().hex[:8]}",
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _url(sample_proposal, action):
    return f"/api/proposals/{sample_proposal['id']}/{READ_ROUTES[action][0]}"


@pytest.mark.parametrize("action", ACTIONS)
def test_policy_read_roles(action):
    for role in ALL_ROLES:
        assert is_role_allowed(role, action)
    assert not is_role_allowed(None, action)
    assert not is_role_allowed("unknown", action)


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("role", ALL_ROLES)
def test_read_allows_policy_roles(client, db_session, sample_proposal, monkeypatch, action, role):
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=role)

    response = client.get(_url(sample_proposal, action), headers=_bearer(token))

    assert response.status_code == READ_ROUTES[action][1], response.text


@pytest.mark.parametrize("action", ACTIONS)
def test_read_requires_bearer_when_user_auth_enabled(client, sample_proposal, monkeypatch, action):
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.get(_url(sample_proposal, action))

    assert response.status_code == 401, response.text


@pytest.mark.parametrize("action", ACTIONS)
def test_read_rejects_invalid_bearer(client, sample_proposal, monkeypatch, action):
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.get(_url(sample_proposal, action), headers=_bearer("not-a-real-token"))

    assert response.status_code == 401, response.text


@pytest.mark.parametrize("action", ACTIONS)
def test_read_preserves_shared_token_compatibility(client, sample_proposal, monkeypatch, action):
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = client.get(
        _url(sample_proposal, action), headers={"X-ReleaseGuard-Token": "shared-secret"}
    )

    assert response.status_code == READ_ROUTES[action][1], response.text


@pytest.mark.parametrize("action", ACTIONS)
def test_read_local_dev_behavior_when_user_auth_unset(client, sample_proposal, action):
    response = client.get(_url(sample_proposal, action))

    assert response.status_code == READ_ROUTES[action][1], response.text
