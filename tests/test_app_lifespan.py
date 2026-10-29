"""ReleaseGuard lifespan and health endpoint tests."""
import pytest


class TestHealthEndpoint:
    """Tests for /health endpoint with lifespan initialization."""

    def test_health_returns_200(self, client):
        """Health endpoint should return HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_includes_status_healthy(self, client):
        """Health endpoint should include status='healthy'."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"

    def test_health_includes_version(self, client):
        """Health endpoint should include version='1.0.0'."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("version") == "1.0.0"
