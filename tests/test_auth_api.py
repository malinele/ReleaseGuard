"""Authentication API tests for KI-001 auth foundation."""
import pytest

from app.services.user_service import UserService


@pytest.fixture(autouse=True)
def _isolate_releaseguard_token(monkeypatch):
    """Keep auth API tests independent from the shared API token guard."""
    monkeypatch.delenv("RELEASEGUARD_WRITE_TOKEN", raising=False)


def _create_user(db_session, username="alice", password="correct-password"):
    return UserService.create_user(
        db_session,
        username=username,
        password=password,
        display_name="Alice Example",
    )


def _login(client, username="alice", password="correct-password"):
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )


def test_login_returns_bearer_token_for_valid_active_user(client, db_session):
    """POST /api/auth/login returns a raw bearer token only after valid credentials."""
    _create_user(db_session)

    response = _login(client)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["access_token"] != "correct-password"
    assert body["expires_at"]


def test_login_rejects_wrong_password(client, db_session):
    """Invalid credentials must not create a session."""
    _create_user(db_session)

    response = _login(client, password="wrong-password")

    assert response.status_code == 401


def test_login_rejects_unknown_user(client):
    """Unknown users must receive the same generic auth failure."""
    response = _login(client, username="missing")

    assert response.status_code == 401


def test_me_requires_bearer_token(client):
    """GET /api/auth/me requires Authorization: Bearer <token>."""
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_rejects_invalid_token(client):
    """Invalid bearer tokens must not authenticate a user."""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401


def test_me_returns_current_user_for_valid_token(client, db_session):
    """A valid session token resolves to the current user identity."""
    user = _create_user(db_session)
    login_response = _login(client)
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == user.id
    assert body["username"] == "alice"
    assert body["display_name"] == "Alice Example"
    assert body["is_active"] is True


def test_logout_revokes_current_session(client, db_session):
    """POST /api/auth/logout revokes the bearer token used for the request."""
    _create_user(db_session)
    token = _login(client).json()["access_token"]

    logout_response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert logout_response.status_code == 200, logout_response.text
    assert logout_response.json() == {"status": "logged_out"}
    assert me_response.status_code == 401


def test_logout_requires_valid_session(client):
    """Logout must reject missing or invalid session tokens."""
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": "Bearer no-session"},
    )

    assert response.status_code == 401


def test_login_open_when_shared_releaseguard_token_is_configured(client, db_session, monkeypatch):
    """The login endpoint remains reachable without X-ReleaseGuard-Token."""
    _create_user(db_session)
    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "shared-token")

    response = _login(client)

    assert response.status_code == 200, response.text
    assert response.json()["access_token"]
