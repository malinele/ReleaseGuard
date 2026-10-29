"""ReleaseGuard opt-in write-token guard tests (KI-001 narrow mitigation).

These tests use the shared ``client`` fixture from ``tests/conftest.py``.
They must NOT instantiate ``TestClient`` directly, must NOT create a
SQLAlchemy engine/session directly, must NOT call ``Base.metadata.create_all``,
and must NOT import ``app.main`` as a separate app instance.
"""
import pytest


@pytest.fixture(autouse=True)
def _isolate_releaseguard_token(monkeypatch):
    """Ensure each test starts with RELEASEGUARD_WRITE_TOKEN unset.

    Individual tests opt-in by calling ``monkeypatch.setenv`` as needed.
    """
    monkeypatch.delenv("RELEASEGUARD_WRITE_TOKEN", raising=False)
    return None


def test_get_api_projects_works_without_token(client):
    """GET /api/projects must never require the write token."""
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_post_api_projects_works_when_token_unset(client):
    """POST /api/projects must work in local-dev when env token is unset/blank."""
    response = client.post(
        "/api/projects",
        json={"name": "NoToken Project", "description": "created without a token"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "NoToken Project"


def test_post_api_projects_401_when_token_set_and_header_missing(client, monkeypatch):
    """With env token set, POST /api/projects without header must return 401."""
    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "s3cret")
    response = client.post(
        "/api/projects",
        json={"name": "Should Fail", "description": "missing header"},
    )
    assert response.status_code == 401


def test_post_api_projects_401_when_token_set_and_header_wrong(client, monkeypatch):
    """With env token set, POST /api/projects with a wrong header must return 401."""
    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "s3cret")
    response = client.post(
        "/api/projects",
        json={"name": "Should Fail", "description": "wrong header"},
        headers={"X-ReleaseGuard-Token": "not-the-right-one"},
    )
    assert response.status_code == 401


def test_post_api_projects_succeeds_with_correct_token(client, monkeypatch):
    """With env token set, POST /api/projects + correct header must succeed."""
    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "s3cret")
    response = client.post(
        "/api/projects",
        json={"name": "WithToken Project", "description": "correct token"},
        headers={"X-ReleaseGuard-Token": "s3cret"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["name"] == "WithToken Project"


def test_health_remains_open_with_token_set(client, monkeypatch):
    """GET /health must never require the write token, even when the token is set."""
    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "s3cret")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def _create_project_for_auth_tests(client, name):
    """Create a project via POST /api/projects while the write token is unset.

    The shared autouse ``_isolate_releaseguard_token`` fixture guarantees
    ``RELEASEGUARD_WRITE_TOKEN`` is unset at the start of every test, so this
    POST is expected to succeed and return the freshly created project record.
    The helper keeps the new PUT/DELETE tests self-contained and avoids any
    direct TestClient, engine, or session construction in this module.
    """
    response = client.post(
        "/api/projects",
        json={"name": name, "description": "fixture project for KI-001 write-auth tests"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_put_api_project_401_when_token_set_and_header_missing(client, monkeypatch):
    """With env token set, PUT /api/projects/{id} without header must return 401."""
    project = _create_project_for_auth_tests(client, name="PUT Missing Header")
    project_id = project["id"]

    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "s3cret")
    response = client.put(
        f"/api/projects/{project_id}",
        json={"name": "PUT Missing Header Renamed", "description": "should fail"},
    )
    assert response.status_code == 401, response.text


def test_put_api_project_succeeds_with_correct_token(client, monkeypatch):
    """With env token set, PUT /api/projects/{id} + correct header must succeed."""
    project = _create_project_for_auth_tests(client, name="PUT With Token")
    project_id = project["id"]

    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "s3cret")
    response = client.put(
        f"/api/projects/{project_id}",
        json={"name": "PUT With Token Renamed", "description": "updated"},
        headers={"X-ReleaseGuard-Token": "s3cret"},
    )
    assert 200 <= response.status_code < 300, response.text
    body = response.json()
    assert body["name"] == "PUT With Token Renamed"


def test_delete_api_project_401_when_token_set_and_header_missing(client, monkeypatch):
    """With env token set, DELETE /api/projects/{id} without header must return 401."""
    project = _create_project_for_auth_tests(client, name="DELETE Missing Header")
    project_id = project["id"]

    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "s3cret")
    response = client.delete(f"/api/projects/{project_id}")
    assert response.status_code == 401, response.text


def test_delete_api_project_succeeds_with_correct_token(client, monkeypatch):
    """With env token set, DELETE /api/projects/{id} + correct header must succeed."""
    project = _create_project_for_auth_tests(client, name="DELETE With Token")
    project_id = project["id"]

    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "s3cret")
    response = client.delete(
        f"/api/projects/{project_id}",
        headers={"X-ReleaseGuard-Token": "s3cret"},
    )
    assert 200 <= response.status_code < 300, response.text


# --- KI-001 strengthening: GET /api/projects must be guarded when token is set ---


def test_get_api_projects_open_when_token_unset(client, monkeypatch):
    """GET /api/projects is open when RELEASEGUARD_WRITE_TOKEN is unset/blank."""
    monkeypatch.delenv("RELEASEGUARD_WRITE_TOKEN", raising=False)
    response = client.get("/api/projects")
    assert response.status_code == 200


def test_get_api_projects_401_when_token_set_header_missing(client, monkeypatch):
    """GET /api/projects returns 401 when token is set and header is missing."""
    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "secret-token")
    response = client.get("/api/projects")
    assert response.status_code == 401


def test_get_api_projects_401_when_token_set_header_wrong(client, monkeypatch):
    """GET /api/projects returns 401 when token is set and header is wrong."""
    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "secret-token")
    response = client.get("/api/projects", headers={"X-ReleaseGuard-Token": "wrong-token"})
    assert response.status_code == 401


def test_get_api_projects_succeeds_with_correct_token(client, monkeypatch):
    """GET /api/projects succeeds when token is set and header matches."""
    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "secret-token")
    response = client.get("/api/projects", headers={"X-ReleaseGuard-Token": "secret-token"})
    assert response.status_code == 200


SENSITIVE_READ_ENDPOINTS = (
    "/api/audit/export",
    "/api/traceability",
    "/api/release-readiness",
)


@pytest.mark.parametrize("endpoint", SENSITIVE_READ_ENDPOINTS)
def test_sensitive_read_api_401_when_token_set_header_missing(client, monkeypatch, endpoint):
    """Sensitive read-only API endpoints require the token when it is configured."""
    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "secret-token")
    response = client.get(endpoint)
    assert response.status_code == 401


@pytest.mark.parametrize("endpoint", SENSITIVE_READ_ENDPOINTS)
def test_sensitive_read_api_succeeds_with_correct_token(client, monkeypatch, endpoint):
    """Sensitive read-only API endpoints remain usable with the correct token."""
    monkeypatch.setenv("RELEASEGUARD_WRITE_TOKEN", "secret-token")
    response = client.get(endpoint, headers={"X-ReleaseGuard-Token": "secret-token"})
    assert 200 <= response.status_code < 300, response.text
