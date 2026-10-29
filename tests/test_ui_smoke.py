"""Smoke tests: every read-only UI page renders as HTML with seeded data."""

import pytest

from app.auth import USER_AUTH_ENV, WRITE_TOKEN_ENV


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Run with auth env controls disabled so pages are reachable."""
    monkeypatch.delenv(USER_AUTH_ENV, raising=False)
    monkeypatch.delenv(WRITE_TOKEN_ENV, raising=False)


STATIC_PAGES = [
    "/",
    "/login",
    "/projects",
    "/evidence",
    "/requirements",
    "/traceability",
    "/audit",
]


@pytest.mark.parametrize("path", STATIC_PAGES)
def test_static_page_renders_html_on_empty_database(client, path):
    """List and dashboard pages return 200 HTML even with no data."""
    response = client.get(path)

    assert response.status_code == 200, response.text
    assert "text/html" in response.headers["content-type"]
    assert "<html" in response.text.lower()


@pytest.mark.parametrize("path", STATIC_PAGES)
def test_static_page_renders_html_with_seeded_data(
    client, sample_requirement, sample_proposal, path
):
    """List and dashboard pages still render once records exist."""
    response = client.get(path)

    assert response.status_code == 200, response.text
    assert "text/html" in response.headers["content-type"]


def test_detail_pages_render_for_seeded_records(
    client, sample_project, sample_requirement, sample_proposal
):
    """Project, requirement, and proposal detail pages render with data."""
    paths = [
        f"/projects/{sample_project['id']}",
        f"/requirements/{sample_requirement['id']}",
        f"/proposals/{sample_proposal['id']}",
    ]

    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, f"{path}: {response.text}"
        assert "text/html" in response.headers["content-type"]


def test_project_page_shows_project_name(client, sample_project):
    """The projects list includes the created project's name."""
    response = client.get("/projects")

    assert sample_project["name"] in response.text


ENUM_REPR_PREFIXES = [
    "WorkflowStatus.",
    "RiskLevel.",
    "Priority.",
    "TestType.",
    "TestResult.",
    "Decision.",
    "AuditAction.",
]


def test_pages_do_not_leak_enum_reprs(
    client, sample_project, sample_requirement, sample_proposal
):
    """Dashboard and proposal detail show enum values, not Python reprs."""
    for path in ["/", f"/proposals/{sample_proposal['id']}"]:
        response = client.get(path)

        assert response.status_code == 200, f"{path}: {response.text}"
        for prefix in ENUM_REPR_PREFIXES:
            assert prefix not in response.text, f"{path} leaks {prefix}"


@pytest.mark.parametrize(
    "path",
    ["/projects/99999", "/requirements/99999", "/proposals/99999"],
)
def test_missing_detail_record_returns_404(client, path):
    """Unknown ids yield 404 rather than a server error."""
    response = client.get(path)

    assert response.status_code == 404
