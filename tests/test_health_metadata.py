"""Test health endpoint metadata responses."""


def test_health_endpoint_returns_healthy_status(client):
    """Verify /health returns status=healthy."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_health_endpoint_returns_version(client):
    """Verify /health returns version=1.0.0."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["version"] == "1.0.0"


def test_health_version_matches_package_version(client):
    """Verify /health and the OpenAPI schema both use app.__version__."""
    from app import __version__

    assert client.get("/health").json()["version"] == __version__
    assert client.get("/openapi.json").json()["info"]["version"] == __version__
