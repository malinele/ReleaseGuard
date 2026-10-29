"""Tests for case-insensitive q filtering on GET /api/projects and GET /api/requirements (KI-005)."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.database import Base, get_db
import app.main as app_main


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_factory()

    app_main.init_db = lambda: None
    app_main.app.dependency_overrides[get_db] = lambda: db

    with TestClient(app_main.app) as test_client:
        yield test_client

    app_main.app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _create_project(client, name, description=""):
    return client.post(
        "/api/projects",
        json={"name": name, "description": description},
    ).json()


def _create_requirement(client, project_id, requirement_id, title, description=""):
    return client.post(
        "/api/requirements",
        json={
            "project_id": project_id,
            "requirement_id": requirement_id,
            "title": title,
            "description": description,
            "priority": "medium",
            "status": "active",
        },
    ).json()


class TestProjectSearch:
    def test_q_substring_case_insensitive_name(self, client):
        _create_project(client, "Alpha Billing", "Revenue search term")
        _create_project(client, "Beta Ops", "Operations")
        response = client.get("/api/projects", params={"q": "alpha"})
        assert [p["name"] for p in response.json()] == ["Alpha Billing"]

    def test_q_substring_case_insensitive_uppercase(self, client):
        _create_project(client, "Alpha Billing", "Revenue search term")
        _create_project(client, "Beta Ops", "Operations")
        response = client.get("/api/projects", params={"q": "ALPHA"})
        assert [p["name"] for p in response.json()] == ["Alpha Billing"]

    def test_q_matches_description(self, client):
        _create_project(client, "Alpha Billing", "Revenue search term")
        _create_project(client, "Beta Ops", "Operations")
        response = client.get("/api/projects", params={"q": "revenue"})
        assert [p["name"] for p in response.json()] == ["Alpha Billing"]

    def test_q_no_match_returns_empty(self, client):
        _create_project(client, "Alpha Billing", "Revenue search term")
        _create_project(client, "Beta Ops", "Operations")
        response = client.get("/api/projects", params={"q": "missing"})
        assert response.json() == []

    def test_no_q_returns_all(self, client):
        _create_project(client, "Alpha Billing", "Revenue search term")
        _create_project(client, "Beta Ops", "Operations")
        response = client.get("/api/projects")
        names = sorted(p["name"] for p in response.json())
        assert names == ["Alpha Billing", "Beta Ops"]

    def test_empty_q_returns_all(self, client):
        _create_project(client, "Alpha Billing", "Revenue search term")
        _create_project(client, "Beta Ops", "Operations")
        response = client.get("/api/projects", params={"q": ""})
        names = sorted(p["name"] for p in response.json())
        assert names == ["Alpha Billing", "Beta Ops"]

    def test_whitespace_q_returns_all(self, client):
        _create_project(client, "Alpha Billing", "Revenue search term")
        _create_project(client, "Beta Ops", "Operations")
        response = client.get("/api/projects", params={"q": "   "})
        names = sorted(p["name"] for p in response.json())
        assert names == ["Alpha Billing", "Beta Ops"]


class TestRequirementSearch:
    def test_q_substring_case_insensitive_title(self, client):
        project = _create_project(client, "Test Project")
        _create_requirement(client, project["id"], "REQ-AUTH", "Authentication Boundary", "Login control")
        _create_requirement(client, project["id"], "REQ-INV", "Inventory Sync", "Stock updates")
        response = client.get("/api/requirements", params={"q": "auth"})
        assert [r["title"] for r in response.json()] == ["Authentication Boundary"]

    def test_q_substring_case_insensitive_uppercase(self, client):
        project = _create_project(client, "Test Project")
        _create_requirement(client, project["id"], "REQ-AUTH", "Authentication Boundary", "Login control")
        _create_requirement(client, project["id"], "REQ-INV", "Inventory Sync", "Stock updates")
        response = client.get("/api/requirements", params={"q": "AUTH"})
        assert [r["title"] for r in response.json()] == ["Authentication Boundary"]

    def test_q_matches_description(self, client):
        project = _create_project(client, "Test Project")
        _create_requirement(client, project["id"], "REQ-AUTH", "Authentication Boundary", "Login control")
        _create_requirement(client, project["id"], "REQ-INV", "Inventory Sync", "Stock updates")
        response = client.get("/api/requirements", params={"q": "login"})
        assert [r["title"] for r in response.json()] == ["Authentication Boundary"]

    def test_q_matches_requirement_id(self, client):
        project = _create_project(client, "Test Project")
        _create_requirement(client, project["id"], "REQ-AUTH", "Authentication Boundary", "Login control")
        _create_requirement(client, project["id"], "REQ-INV", "Inventory Sync", "Stock updates")
        response = client.get("/api/requirements", params={"q": "req-auth"})
        ids = [r["requirement_id"] for r in response.json()]
        assert "REQ-AUTH" in ids

    def test_q_no_match_returns_empty(self, client):
        project = _create_project(client, "Test Project")
        _create_requirement(client, project["id"], "REQ-AUTH", "Authentication Boundary", "Login control")
        response = client.get("/api/requirements", params={"q": "missing"})
        assert response.json() == []

    def test_no_q_returns_all(self, client):
        project = _create_project(client, "Test Project")
        _create_requirement(client, project["id"], "REQ-AUTH", "Authentication Boundary", "Login control")
        _create_requirement(client, project["id"], "REQ-INV", "Inventory Sync", "Stock updates")
        response = client.get("/api/requirements")
        assert len(response.json()) == 2

    def test_empty_q_returns_all(self, client):
        project = _create_project(client, "Test Project")
        _create_requirement(client, project["id"], "REQ-AUTH", "Authentication Boundary", "Login control")
        _create_requirement(client, project["id"], "REQ-INV", "Inventory Sync", "Stock updates")
        response = client.get("/api/requirements", params={"q": ""})
        assert len(response.json()) == 2

    def test_q_with_project_filter(self, client):
        project_a = _create_project(client, "Project A")
        project_b = _create_project(client, "Project B")
        _create_requirement(client, project_a["id"], "REQ-AUTH", "Authentication", "Login")
        _create_requirement(client, project_b["id"], "REQ-AUTH2", "Authorization", "Permissions")
        response = client.get(
            "/api/requirements",
            params={"q": "auth", "project_id": project_a["id"]},
        )
        assert [r["title"] for r in response.json()] == ["Authentication"]
