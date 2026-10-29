"""RBAC enforcement tests for POST release-decision."""
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
    user = UserService.create_user(
        db_session,
        username=f"{role}-release-user",
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


def _decision_payload(sample_proposal):
    return {
        "proposal_id": sample_proposal["id"],
        "decision": "approved",
        "decision_maker": "Release Manager",
        "decision_notes": "Approved by test.",
    }


def _post_release_decision(client, sample_proposal, headers=None):
    return client.post(
        f"/api/proposals/{sample_proposal['id']}/release-decision",
        json=_decision_payload(sample_proposal),
        headers=headers or {},
    )


@pytest.mark.parametrize("allowed_role", [ROLE_OWNER, ROLE_ADMIN])
def test_release_decision_post_allows_owner_and_admin_bearer(
    client, db_session, sample_proposal, monkeypatch, allowed_role
):
    """Owner/admin bearer sessions can create a release decision when auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=allowed_role)

    response = _post_release_decision(
        client,
        sample_proposal,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["decision"] == "approved"


@pytest.mark.parametrize("denied_role", [ROLE_FINANCE, ROLE_SUPPORT, ROLE_VIEWER])
def test_release_decision_post_denies_non_decider_roles(
    client, db_session, sample_proposal, monkeypatch, denied_role
):
    """Finance/support/viewer bearer sessions are authenticated but not authorized."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=denied_role)

    response = _post_release_decision(
        client,
        sample_proposal,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403, response.text


def test_release_decision_post_requires_bearer_when_user_auth_enabled(
    client, sample_proposal, monkeypatch
):
    """Missing bearer session returns 401 when user auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = _post_release_decision(client, sample_proposal)

    assert response.status_code == 401, response.text


def test_release_decision_post_rejects_invalid_bearer(
    client, sample_proposal, monkeypatch
):
    """Invalid bearer token returns 401 when user auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = _post_release_decision(
        client,
        sample_proposal,
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401, response.text


def test_release_decision_post_preserves_shared_token_compatibility(
    client, sample_proposal, monkeypatch
):
    """A valid shared token still authorizes the release decision POST."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = _post_release_decision(
        client,
        sample_proposal,
        headers={"X-ReleaseGuard-Token": "shared-secret"},
    )

    assert response.status_code == 201, response.text


def test_release_decision_get_not_gated_by_this_rbac_slice(
    client, db_session, sample_proposal, monkeypatch
):
    """GET release-decision behavior is intentionally unchanged by this slice."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=ROLE_VIEWER)

    response = client.get(
        f"/api/proposals/{sample_proposal['id']}/release-decision",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


def test_release_decision_post_local_dev_behavior_when_user_auth_unset(
    client, sample_proposal
):
    """When user auth is not required, POST keeps existing local-dev behavior."""
    response = _post_release_decision(client, sample_proposal)

    assert response.status_code == 201, response.text
