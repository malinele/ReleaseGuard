"""ReleaseGuard API smoke tests - quality gate for minimal ReleaseGuard API."""

import pytest


class TestHealthEndpoint:
    """Smoke tests for health endpoint."""

    def test_root_health_returns_200(self, client):
        """Root endpoint should return 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_api_health_returns_200(self, client):
        """API health endpoint should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200


class TestProjectFixtureData:
    """Smoke tests for project fixture data."""

    def test_sample_project_fixture_returns_valid_data(self, client, sample_project):
        """Sample project fixture should return valid project data."""
        assert sample_project is not None
        assert "id" in sample_project
        assert "name" in sample_project
        assert sample_project["name"] == "Test Project"

    def test_get_projects_returns_list(self, client, sample_project):
        """GET /api/projects should return list of projects."""
        response = client.get("/api/projects")
        assert response.status_code == 200
        projects = response.json()
        assert isinstance(projects, list)
        assert len(projects) >= 1


class TestProposalFixtureData:
    """Smoke tests for proposal fixture data."""

    def test_sample_proposal_fixture_returns_valid_data(self, client, sample_proposal):
        """Sample proposal fixture should return valid proposal data."""
        assert sample_proposal is not None
        assert "id" in sample_proposal
        assert "proposal_id" in sample_proposal
        assert sample_proposal["proposal_id"] == "PROP-TEST-001"

    def test_get_proposals_returns_list(self, client, sample_proposal):
        """GET /api/proposals should return list of proposals."""
        response = client.get("/api/proposals")
        assert response.status_code == 200
        proposals = response.json()
        assert isinstance(proposals, list)
        assert len(proposals) >= 1


class TestReleaseReadinessAggregate:
    """Smoke tests for release readiness aggregate response."""

    def test_release_readiness_returns_aggregate_response(self, client, sample_proposal):
        """Release readiness endpoint should return aggregate response with summary stats."""
        response = client.get("/api/release-readiness")
        assert response.status_code == 200
        data = response.json()
        # Verify aggregate fields exist
        assert "total_proposals" in data
        assert "release_ready" in data
        assert "blocked" in data
        assert "items" in data
        assert isinstance(data["items"], list)
        # Verify counts are integers
        assert isinstance(data["total_proposals"], int)
        assert isinstance(data["release_ready"], int)
        assert isinstance(data["blocked"], int)

    def test_release_readiness_includes_proposal_item(self, client, sample_proposal):
        """Release readiness should include proposal in items list."""
        response = client.get("/api/release-readiness")
        assert response.status_code == 200
        data = response.json()
        assert data["total_proposals"] >= 1
        proposal_ids = [item["proposal_id"] for item in data["items"]]
        assert "PROP-TEST-001" in proposal_ids


class TestAuditExportAggregate:
    """Smoke tests for audit export aggregate response."""

    def test_audit_export_returns_aggregate_response(self, client, sample_project, sample_proposal):
        """Audit export endpoint should return aggregate response with summary stats."""
        response = client.get("/api/audit/export")
        assert response.status_code == 200
        data = response.json()
        # Verify aggregate fields exist
        assert "total_events" in data
        assert "filters" in data
        assert "summary" in data
        assert "events" in data
        assert isinstance(data["summary"], dict)
        # Verify summary contains expected aggregation keys
        assert "by_action" in data["summary"]
        assert "by_entity_type" in data["summary"]
        assert "actors" in data["summary"]

    def test_audit_export_respects_limit_param(self, client, sample_project, sample_proposal):
        """Audit export should respect limit query parameter."""
        response = client.get("/api/audit/export?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["filters"]["limit"] == 5
        assert len(data["events"]) <= 5

class TestAuditEventIndexes:
    """Quality gate tests for AuditEvent index coverage (KI-010)."""

    def test_audit_events_table_has_indexes_for_common_filters(self, db_session):
        """Verify audit_events table has indexes covering timestamp, actor, action, entity_type, entity_id."""
        from sqlalchemy import inspect
        from sqlalchemy.engine import Engine

        engine = db_session.bind
        assert isinstance(engine, Engine), "db_session must be bound to an Engine"

        inspector = inspect(engine)
        indexes = inspector.get_indexes("audit_events")
        indexed_columns = {idx["column_names"][0] for idx in indexes}

        required_indexes = {"timestamp", "actor", "action", "entity_type", "entity_id"}
        missing = required_indexes - indexed_columns

        assert not missing, f"Missing indexes on audit_events for columns: {missing}"
