"""RBAC enforcement tests for proposal requirement link/unlink endpoints."""
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

ACTION = "proposal_requirements:write"
ALLOWED_ROLES = [ROLE_OWNER, ROLE_ADMIN, ROLE_FINANCE]
DENIED_ROLES = [ROLE_SUPPORT, ROLE_VIEWER]


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Start each test with auth env controls disabled."""
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)
    monkeypatch.delenv(WRITE_TOKEN_ENV, raising=False)


def _create_user_token(db_session, *, role):
    user = UserService.create_user(
        db_session,
        username=f"{role}-proposalreq-user-{uuid.uuid4().hex[:8]}",
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _url(sample_proposal):
    return f"/api/proposals/{sample_proposal['id']}/requirements"


def _payload(sample_proposal, sample_requirement):
    return {
        "proposal_id": sample_proposal["id"],
        "requirement_id": sample_requirement["id"],
    }


def _seed_link(client, sample_proposal, sample_requirement):
    """Create a link while user auth is disabled (local dev mode)."""
    response = client.post(_url(sample_proposal), json=_payload(sample_proposal, sample_requirement))
    assert response.status_code == 201, response.text


def test_policy_proposal_requirements_write_roles():
    for role in ALLOWED_ROLES:
        assert is_role_allowed(role, ACTION)
    for role in DENIED_ROLES:
        assert not is_role_allowed(role, ACTION)


@pytest.mark.parametrize("allowed_role", ALLOWED_ROLES)
def test_link_allows_policy_roles(
    client, db_session, sample_proposal, sample_requirement, monkeypatch, allowed_role
):
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=allowed_role)

    response = client.post(
        _url(sample_proposal),
        json=_payload(sample_proposal, sample_requirement),
        headers=_bearer(token),
    )

    assert response.status_code == 201, response.text


@pytest.mark.parametrize("denied_role", DENIED_ROLES)
def test_link_denies_other_roles(
    client, db_session, sample_proposal, sample_requirement, monkeypatch, denied_role
):
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=denied_role)

    response = client.post(
        _url(sample_proposal),
        json=_payload(sample_proposal, sample_requirement),
        headers=_bearer(token),
    )

    assert response.status_code == 403, response.text


def test_link_requires_bearer_when_user_auth_enabled(
    client, sample_proposal, sample_requirement, monkeypatch
):
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.post(_url(sample_proposal), json=_payload(sample_proposal, sample_requirement))

    assert response.status_code == 401, response.text


def test_link_rejects_invalid_bearer(client, sample_proposal, sample_requirement, monkeypatch):
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.post(
        _url(sample_proposal),
        json=_payload(sample_proposal, sample_requirement),
        headers=_bearer("not-a-real-token"),
    )

    assert response.status_code == 401, response.text


def test_link_preserves_shared_token_compatibility(
    client, sample_proposal, sample_requirement, monkeypatch
):
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = client.post(
        _url(sample_proposal),
        json=_payload(sample_proposal, sample_requirement),
        headers={"X-ReleaseGuard-Token": "shared-secret"},
    )

    assert response.status_code == 201, response.text


def test_link_local_dev_behavior_when_user_auth_unset(client, sample_proposal, sample_requirement):
    response = client.post(_url(sample_proposal), json=_payload(sample_proposal, sample_requirement))

    assert response.status_code == 201, response.text


def test_unlink_allows_and_denies_by_role(
    client, db_session, sample_proposal, sample_requirement, monkeypatch
):
    _seed_link(client, sample_proposal, sample_requirement)
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    url = f"{_url(sample_proposal)}/{sample_requirement['id']}"

    denied = _create_user_token(db_session, role=ROLE_VIEWER)
    assert client.delete(url, headers=_bearer(denied)).status_code == 403
    assert client.delete(url).status_code == 401

    allowed = _create_user_token(db_session, role=ROLE_ADMIN)
    response = client.delete(url, headers=_bearer(allowed))
    assert response.status_code == 204, response.text


def test_get_not_gated_by_write_permission(client, db_session, sample_proposal, monkeypatch):
    """GET is a read path; a viewer is not rejected by the write gate."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=ROLE_VIEWER)

    response = client.get(_url(sample_proposal), headers=_bearer(token))

    assert response.status_code == 200, response.text
