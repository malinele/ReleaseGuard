"""Opt-in bearer-session API guard tests for KI-001."""
import pytest

from app.services.user_service import UserService


@pytest.fixture(autouse=True)
def _isolate_auth_env(monkeypatch):
    """Start each test with both auth env controls disabled."""
    monkeypatch.delenv("RELEASEGUARD_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("RELEASEGUARD_REQUIRE_USER_AUTH", raising=False)


def _create_user_and_login(client, db_session):
    UserService.create_user(
        db_session,
        username="alice",
        password="correct-password",
        display_name="Alice Example",
    )
    response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "correct-password"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_domain_api_default_local_dev_behavior_remains_open(client):
    """When no auth env is configured, existing local-dev API behavior remains open."""
    response = client.get("/api/projects")

    assert response.status_code == 200


def test_domain_api_requires_bearer_when_user_auth_enabled(client, monkeypatch):
    """Opt-in user auth blocks non-auth /api routes without a bearer session."""
    monkeypatch.setenv("RELEASEGUARD_REQUIRE_USER_AUTH", "true")

    response = client.get("/api/projects")

    assert response.status_code == 401


def test_domain_api_accepts_valid_bearer_when_user_auth_enabled(client, db_session, monkeypatch):
    """A valid local user session authorizes non-auth /api routes."""
    token = _create_user_and_login(client, db_session)
    monkeypatch.setenv("RELEASEGUARD_REQUIRE_USER_AUTH", "true")

    response = client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text


def test_domain_api_rejects_invalid_bearer_when_user_auth_enabled(client, monkeypatch):
    """Invalid bearer tokens do not satisfy the opt-in user auth guard."""
    monkeypatch.setenv("RELEASEGUARD_REQUIRE_USER_AUTH", "true")

    response = client.get(
        "/api/projects",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_auth_login_remains_open_when_user_auth_enabled(client, db_session, monkeypatch):
    """The shared API guard must not block /api/auth/login."""
    UserService.create_user(
        db_session,
        username="alice",
        password="correct-password",
        display_name="Alice Example",
    )
    monkeypatch.setenv("RELEASEGUARD_REQUIRE_USER_AUTH", "true")

    response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "correct-password"},
    )

    assert response.status_code == 200, response.text


def test_shared_token_still_authorizes_when_user_auth_enabled(client, monkeypatch):
    """Existing shared-token integrations keep working under user-auth opt-in."""
    monkeypatch.setenv("RELEASEGUARD_REQUIRE_USER_AUTH", "true")
    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "shared-token")

    response = client.get(
        "/api/projects",
        headers={"X-ReleaseGuard-Token": "shared-token"},
    )

    assert response.status_code == 200, response.text


def test_shared_token_guard_behavior_unchanged_when_user_auth_disabled(client, monkeypatch):
    """Existing RELEASEGUARD_WRITE_TOKEN-only behavior remains unchanged."""
    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "shared-token")

    missing = client.get("/api/projects")
    present = client.get(
        "/api/projects",
        headers={"X-ReleaseGuard-Token": "shared-token"},
    )

    assert missing.status_code == 401
    assert present.status_code == 200
