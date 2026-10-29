"""RBAC enforcement tests for test evidence write endpoints."""
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

ALLOWED_ROLES = [ROLE_OWNER, ROLE_ADMIN, ROLE_SUPPORT]
DENIED_ROLES = [ROLE_FINANCE, ROLE_VIEWER]


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Start each test with auth env controls disabled."""
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)
    monkeypatch.delenv(WRITE_TOKEN_ENV, raising=False)


def _create_user_token(db_session, *, role):
    username = f"{role}-testevid-user-{uuid.uuid4().hex[:8]}"
    user = UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _create_url(sample_proposal):
    return f"/api/proposals/{sample_proposal['id']}/test-evidence"


def _payload(sample_proposal):
    return {
        "proposal_id": sample_proposal["id"],
        "test_type": "unit",
        "command_or_procedure": "pytest -q tests/",
        "result": "passed",
    }


def _seed_evidence(client, sample_proposal):
    """Create an evidence record while user auth is disabled (local dev mode)."""
    response = client.post(_create_url(sample_proposal), json=_payload(sample_proposal))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_policy_test_evidence_write_roles():
    for role in ALLOWED_ROLES:
        assert is_role_allowed(role, "test_evidence:write")
    for role in DENIED_ROLES:
        assert not is_role_allowed(role, "test_evidence:write")


@pytest.mark.parametrize("allowed_role", ALLOWED_ROLES)
def test_create_allows_policy_roles(client, db_session, sample_proposal, monkeypatch, allowed_role):
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=allowed_role)

    response = client.post(
        _create_url(sample_proposal), json=_payload(sample_proposal), headers=_bearer(token)
    )

    assert response.status_code == 201, response.text


@pytest.mark.parametrize("denied_role", DENIED_ROLES)
def test_create_denies_other_roles(client, db_session, sample_proposal, monkeypatch, denied_role):
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=denied_role)

    response = client.post(
        _create_url(sample_proposal), json=_payload(sample_proposal), headers=_bearer(token)
    )

    assert response.status_code == 403, response.text


def test_create_requires_bearer_when_user_auth_enabled(client, sample_proposal, monkeypatch):
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.post(_create_url(sample_proposal), json=_payload(sample_proposal))

    assert response.status_code == 401, response.text


def test_create_rejects_invalid_bearer(client, sample_proposal, monkeypatch):
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.post(
        _create_url(sample_proposal),
        json=_payload(sample_proposal),
        headers=_bearer("not-a-real-token"),
    )

    assert response.status_code == 401, response.text


def test_create_preserves_shared_token_compatibility(client, sample_proposal, monkeypatch):
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = client.post(
        _create_url(sample_proposal),
        json=_payload(sample_proposal),
        headers={"X-ReleaseGuard-Token": "shared-secret"},
    )

    assert response.status_code == 201, response.text


def test_create_local_dev_behavior_when_user_auth_unset(client, sample_proposal):
    response = client.post(_create_url(sample_proposal), json=_payload(sample_proposal))

    assert response.status_code == 201, response.text


def test_update_allows_and_denies_by_role(client, db_session, sample_proposal, monkeypatch):
    evidence_id = _seed_evidence(client, sample_proposal)
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    url = f"/api/test-evidence/{evidence_id}"
    body = {"evidence_notes": "updated"}

    denied = _create_user_token(db_session, role=ROLE_VIEWER)
    assert client.put(url, json=body, headers=_bearer(denied)).status_code == 403
    assert client.put(url, json=body).status_code == 401

    allowed = _create_user_token(db_session, role=ROLE_ADMIN)
    response = client.put(url, json=body, headers=_bearer(allowed))
    assert response.status_code == 200, response.text


def test_delete_allows_and_denies_by_role(client, db_session, sample_proposal, monkeypatch):
    evidence_id = _seed_evidence(client, sample_proposal)
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    url = f"/api/test-evidence/{evidence_id}"

    denied = _create_user_token(db_session, role=ROLE_FINANCE)
    assert client.delete(url, headers=_bearer(denied)).status_code == 403
    assert client.delete(url).status_code == 401

    allowed = _create_user_token(db_session, role=ROLE_OWNER)
    response = client.delete(url, headers=_bearer(allowed))
    assert response.status_code == 204, response.text


def test_get_not_gated_by_write_permission(client, db_session, sample_proposal, monkeypatch):
    """GET is a read path; a viewer is not rejected by the write gate."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=ROLE_VIEWER)

    response = client.get(_create_url(sample_proposal), headers=_bearer(token))

    assert response.status_code == 200, response.text
