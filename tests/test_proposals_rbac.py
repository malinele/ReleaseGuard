"""RBAC enforcement tests for proposal write endpoints."""
import pytest

from app.auth import USER_AUTH_ENV, WRITE_TOKEN_ENV
from app.models.proposal import WorkflowStatus
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
        username=f"{role}-proposal-user",
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


def _proposal_create_payload(sample_project, proposal_id="PROP-RBAC-NEW"):
    return {
        "project_id": sample_project["id"],
        "proposal_id": proposal_id,
        "summary": "RBAC proposal",
        "generated_by": "test",
        "files_expected": [],
        "risk_level": "medium",
    }


def _proposal_update_payload():
    return {
        "summary": "Updated by RBAC test",
        "risk_level": "high",
    }


@pytest.mark.parametrize("allowed_role", [ROLE_OWNER, ROLE_ADMIN, ROLE_FINANCE])
def test_create_proposal_allows_policy_roles(client, db_session, sample_project, monkeypatch, allowed_role):
    """owner/admin/finance bearer sessions can create proposals when auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=allowed_role)

    response = client.post(
        "/api/proposals",
        json=_proposal_create_payload(sample_project, proposal_id=f"PROP-{allowed_role.upper()}"),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text


@pytest.mark.parametrize("denied_role", [ROLE_SUPPORT, ROLE_VIEWER])
def test_create_proposal_denies_non_writer_roles(client, db_session, sample_project, monkeypatch, denied_role):
    """support/viewer bearer sessions are authenticated but not authorized."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=denied_role)

    response = client.post(
        "/api/proposals",
        json=_proposal_create_payload(sample_project, proposal_id=f"PROP-{denied_role.upper()}"),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403, response.text


def test_create_proposal_requires_bearer_when_user_auth_enabled(client, sample_project, monkeypatch):
    """Missing bearer session returns 401 when user auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.post(
        "/api/proposals",
        json=_proposal_create_payload(sample_project),
    )

    assert response.status_code == 401, response.text


def test_create_proposal_rejects_invalid_bearer(client, sample_project, monkeypatch):
    """Invalid bearer token returns 401 when user auth is enabled."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.post(
        "/api/proposals",
        json=_proposal_create_payload(sample_project),
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401, response.text


def test_create_proposal_preserves_shared_token_compatibility(client, sample_project, monkeypatch):
    """A valid shared token still authorizes proposal writes."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = client.post(
        "/api/proposals",
        json=_proposal_create_payload(sample_project),
        headers={"X-ReleaseGuard-Token": "shared-secret"},
    )

    assert response.status_code == 201, response.text


def test_update_proposal_requires_writer_role(client, db_session, sample_proposal, monkeypatch):
    """PUT /api/proposals/{id} enforces proposals:write."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    denied_token = _create_user_token(db_session, role=ROLE_VIEWER)
    allowed_token = _create_user_token(db_session, role=ROLE_FINANCE)

    denied = client.put(
        f"/api/proposals/{sample_proposal['id']}",
        json=_proposal_update_payload(),
        headers={"Authorization": f"Bearer {denied_token}"},
    )
    allowed = client.put(
        f"/api/proposals/{sample_proposal['id']}",
        json=_proposal_update_payload(),
        headers={"Authorization": f"Bearer {allowed_token}"},
    )

    assert denied.status_code == 403, denied.text
    assert allowed.status_code == 200, allowed.text


def test_delete_proposal_requires_writer_role(client, db_session, sample_proposal, monkeypatch):
    """DELETE /api/proposals/{id} enforces proposals:write."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    denied_token = _create_user_token(db_session, role=ROLE_SUPPORT)
    allowed_token = _create_user_token(db_session, role=ROLE_ADMIN)

    denied = client.delete(
        f"/api/proposals/{sample_proposal['id']}",
        headers={"Authorization": f"Bearer {denied_token}"},
    )
    allowed = client.delete(
        f"/api/proposals/{sample_proposal['id']}",
        headers={"Authorization": f"Bearer {allowed_token}"},
    )

    assert denied.status_code == 403, denied.text
    assert allowed.status_code == 204, allowed.text


def test_transition_proposal_requires_writer_role(client, db_session, sample_proposal, monkeypatch):
    """POST /api/proposals/{id}/transition enforces proposals:write before workflow validation."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    denied_token = _create_user_token(db_session, role=ROLE_VIEWER)
    allowed_token = _create_user_token(db_session, role=ROLE_OWNER)
    payload = {"target_status": WorkflowStatus.CONTEXT_REVIEW.value, "actor": "test"}

    denied = client.post(
        f"/api/proposals/{sample_proposal['id']}/transition",
        json=payload,
        headers={"Authorization": f"Bearer {denied_token}"},
    )
    allowed = client.post(
        f"/api/proposals/{sample_proposal['id']}/transition",
        json=payload,
        headers={"Authorization": f"Bearer {allowed_token}"},
    )

    assert denied.status_code == 403, denied.text
    assert allowed.status_code not in (401, 403), allowed.text


def test_get_proposals_not_gated_by_proposals_write_slice(client, db_session, monkeypatch):
    """GET proposals remains a read path and is not subject to proposals:write."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=ROLE_VIEWER)

    response = client.get(
        "/api/proposals",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def test_create_proposal_local_dev_behavior_when_user_auth_unset(client, sample_project):
    """When user auth is not required, proposal creation keeps existing local-dev behavior."""
    response = client.post(
        "/api/proposals",
        json=_proposal_create_payload(sample_project),
    )

    assert response.status_code == 201, response.text
