"""Pytest configuration and fixtures for ReleaseGuard tests."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
import app.main as app_main

app = app_main.app


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    """Create a test client with database override."""
    monkeypatch.setattr(app_main, "init_db", lambda: None)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_project(client):
    """Create a sample project for testing."""
    response = client.post(
        "/api/projects",
        json={"name": "Test Project", "description": "A test project"},
    )
    return response.json()


@pytest.fixture
def sample_requirement(client, sample_project):
    """Create a sample requirement for testing."""
    response = client.post(
        "/api/requirements",
        json={
            "project_id": sample_project["id"],
            "requirement_id": "REQ-TEST-001",
            "title": "Test Requirement",
            "description": "A test requirement",
            "priority": "medium",
            "status": "active",
        },
    )
    return response.json()


@pytest.fixture
def sample_proposal(client, sample_project):
    """Create a sample proposal for testing."""
    response = client.post(
        "/api/proposals",
        json={
            "project_id": sample_project["id"],
            "proposal_id": "PROP-TEST-001",
            "summary": "Test Proposal Summary",
            "generated_by": "test",
            "files_expected": [],
            "risk_level": "medium",
        },
    )
    return response.json()
