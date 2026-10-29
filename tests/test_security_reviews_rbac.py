"""RBAC enforcement tests for security review write endpoints."""
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


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Start each test with auth env controls disabled."""
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)
    monkeypatch.delenv(WRITE_TOKEN_ENV, raising=False)


def _create_user_token(db_session, *, role):
    username = f"{role}-secreview-user-{uuid.uuid4().hex[:8]}"
    user = UserService.create_user(
        db_session,
        username=username,
        password="correct-password",
        role=role,
    )
    return SessionService.create_session(db_session, user_id=user.id).token


def _url(sample_proposal):
    return f"/api/proposals/{sample_proposal['id']}/security-review"


def _payload(sample_proposal):
    return {"proposal_id": sample_proposal["id"], "status": "pending", "notes": "rbac test"}


def test_policy_security_reviews_write_roles():
    """Only owner/admin hold security_reviews:write."""
    for role in (ROLE_OWNER, ROLE_ADMIN):
        assert is_role_allowed(role, "security_reviews:write")
    for role in (ROLE_FINANCE, ROLE_SUPPORT, ROLE_VIEWER):
        assert not is_role_allowed(role, "security_reviews:write")


@pytest.mark.parametrize("allowed_role", [ROLE_OWNER, ROLE_ADMIN])
def test_create_security_review_allows_policy_roles(client, db_session, sample_proposal, monkeypatch, allowed_role):
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=allowed_role)

    response = client.post(
        _url(sample_proposal),
        json=_payload(sample_proposal),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text


@pytest.mark.parametrize("denied_role", [ROLE_FINANCE, ROLE_SUPPORT, ROLE_VIEWER])
def test_create_security_review_denies_other_roles(client, db_session, sample_proposal, monkeypatch, denied_role):
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=denied_role)

    response = client.post(
        _url(sample_proposal),
        json=_payload(sample_proposal),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403, response.text


def test_create_security_review_requires_bearer_when_user_auth_enabled(client, sample_proposal, monkeypatch):
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.post(_url(sample_proposal), json=_payload(sample_proposal))

    assert response.status_code == 401, response.text


def test_create_security_review_rejects_invalid_bearer(client, sample_proposal, monkeypatch):
    monkeypatch.setenv(USER_AUTH_ENV, "true")

    response = client.post(
        _url(sample_proposal),
        json=_payload(sample_proposal),
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401, response.text


def test_create_security_review_preserves_shared_token_compatibility(client, sample_proposal, monkeypatch):
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    monkeypatch.setenv(WRITE_TOKEN_ENV, "shared-secret")

    response = client.post(
        _url(sample_proposal),
        json=_payload(sample_proposal),
        headers={"X-ReleaseGuard-Token": "shared-secret"},
    )

    assert response.status_code == 201, response.text


def test_get_security_review_not_gated_by_write_permission(client, db_session, sample_proposal, monkeypatch):
    """GET is a read path; a viewer is not rejected with 403 by the write gate."""
    monkeypatch.setenv(USER_AUTH_ENV, "true")
    token = _create_user_token(db_session, role=ROLE_VIEWER)

    response = client.get(
        _url(sample_proposal),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code in (200, 404), response.text


def test_create_security_review_local_dev_behavior_when_user_auth_unset(client, sample_proposal):
    response = client.post(_url(sample_proposal), json=_payload(sample_proposal))

    assert response.status_code == 201, response.text
