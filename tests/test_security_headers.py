

# ---------------------------------------------------------------------------=
# Production-safe response header regressions
# ---------------------------------------------------------------------------=


def test_security_headers_present_on_health_response(client):
    """The /health response carries the production-safe security headers."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"


def test_security_headers_present_on_error_response(client):
    """The middleware also applies to error (404) responses."""
    response = client.get("/this-route-does-not-exist")

    assert response.status_code == 404
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"


def test_referrer_policy_header_present(client):
    """The /health response and error responses carry Referrer-Policy: same-origin."""
    health_response = client.get("/health")

    assert health_response.status_code == 200
    assert health_response.headers.get("Referrer-Policy") == "same-origin"

    error_response = client.get("/this-route-does-not-exist")

    assert error_response.status_code == 404
    assert error_response.headers.get("Referrer-Policy") == "same-origin"
