"""Production auth configuration guard tests."""

import pytest

from app.auth import _production_mode, _user_auth_required
from app.services.user_service import UserService


@pytest.fixture(autouse=True)
def _isolate_auth_env(monkeypatch):
    """Start each test with auth env controls disabled."""
    monkeypatch.delenv("RELEASEGUARD_ENV", raising=False)
    monkeypatch.delenv("RELEASEGUARD_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("RELEASEGUARD_REQUIRE_USER_AUTH", raising=False)


def test_local_dev_auth_behavior_remains_open(client):
    """Default local-dev behavior remains unchanged when env is unset."""
    response = client.get("/api/projects")

    assert _production_mode() is False
    assert _user_auth_required() is False
    assert response.status_code == 200


@pytest.mark.parametrize("value", ["production", "prod"])
def test_production_env_requires_api_auth_by_default(client, monkeypatch, value):
    """Production mode must fail closed instead of leaving protected APIs open."""
    monkeypatch.setenv("RELEASEGUARD_ENV", value)

    response = client.get("/api/projects")

    assert _production_mode() is True
    assert _user_auth_required() is True
    assert response.status_code == 401


def test_production_env_requires_ui_auth_by_default(client, monkeypatch):
    """Production mode must not leave server-rendered UI pages open."""
    monkeypatch.setenv("RELEASEGUARD_ENV", "production")

    response = client.get("/")

    assert response.status_code == 401


def test_production_env_preserves_shared_token_override(client, monkeypatch):
    """Shared-token deployments remain compatible in production mode."""
    monkeypatch.setenv("RELEASEGUARD_ENV", "production")
    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "shared-token")

    api_response = client.get(
        "/api/projects",
        headers={"X-ReleaseGuard-Token": "shared-token"},
    )
    ui_response = client.get(
        "/",
        headers={"X-ReleaseGuard-Token": "shared-token"},
    )

    assert api_response.status_code == 200, api_response.text
    assert ui_response.status_code == 200, ui_response.text


def test_production_env_accepts_bearer_session(client, db_session, monkeypatch):
    """Explicit user-auth production deployments can use bearer sessions."""
    UserService.create_user(
        db_session,
        username="prod-user",
        password="correct-password",
    )
    token_response = client.post(
        "/api/auth/login",
        json={"username": "prod-user", "password": "correct-password"},
    )
    assert token_response.status_code == 200, token_response.text
    token = token_response.json()["access_token"]
    monkeypatch.setenv("RELEASEGUARD_ENV", "production")
    monkeypatch.setenv("RELEASEGUARD_REQUIRE_USER_AUTH", "true")

    response = client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
