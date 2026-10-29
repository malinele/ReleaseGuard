"""Tests for direct requirement/proposal version history."""
from app.models.project import Project
from app.models.proposal import Proposal, RiskLevel, WorkflowStatus
from app.models.requirement import Priority, Requirement, RequirementStatus
from app.schemas.proposal import ProposalUpdate
from app.schemas.requirement import RequirementUpdate
from app.services.proposal_service import ProposalService
from app.services.requirement_service import RequirementService
from app.services.version_history_service import VersionHistoryService


def _create_project(db_session) -> Project:
    project = Project(name="Version History Project", description="Version tests")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def _create_requirement(db_session, project: Project) -> Requirement:
    requirement = Requirement(
        project_id=project.id,
        requirement_id="REQ-VERSION-001",
        title="Original requirement",
        description="Original description",
        priority=Priority.MEDIUM,
        status=RequirementStatus.ACTIVE,
    )
    db_session.add(requirement)
    db_session.commit()
    db_session.refresh(requirement)
    return requirement


def _create_proposal(db_session, project: Project) -> Proposal:
    proposal = Proposal(
        project_id=project.id,
        proposal_id="PROP-VERSION-001",
        summary="Original proposal",
        generated_by="pytest",
        files_expected=[],
        risk_level=RiskLevel.MEDIUM,
        workflow_status=WorkflowStatus.DRAFT,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)
    return proposal


def test_requirement_update_records_direct_version_history(db_session):
    project = _create_project(db_session)
    requirement = _create_requirement(db_session, project)

    updated = RequirementService.update_requirement(
        db_session,
        requirement.id,
        RequirementUpdate(title="Updated requirement"),
        actor="qa",
    )

    assert updated is not None
    versions = VersionHistoryService.list_versions(
        db_session,
        "requirement",
        requirement.id,
    )
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert versions[0].actor == "qa"
    assert "Original requirement" in versions[0].before_summary
    assert "Updated requirement" in versions[0].after_summary


def test_proposal_update_records_incrementing_versions(db_session):
    project = _create_project(db_session)
    proposal = _create_proposal(db_session, project)

    ProposalService.update_proposal(
        db_session,
        proposal.id,
        ProposalUpdate(summary="Second proposal"),
        actor="reviewer",
    )
    ProposalService.update_proposal(
        db_session,
        proposal.id,
        ProposalUpdate(workflow_status=WorkflowStatus.CONTEXT_REVIEW),
        actor="reviewer",
    )

    versions = VersionHistoryService.list_versions(db_session, "proposal", proposal.id)
    assert [version.version_number for version in versions] == [1, 2]
    assert all(version.actor == "reviewer" for version in versions)
    assert "Original proposal" in versions[0].before_summary
    assert "Second proposal" in versions[0].after_summary
    assert "context_review" in versions[1].after_summary


def test_missing_entities_record_no_version_history(db_session):
    missing_requirement = RequirementService.update_requirement(
        db_session,
        999,
        RequirementUpdate(title="Missing"),
        actor="qa",
    )
    missing_proposal = ProposalService.update_proposal(
        db_session,
        999,
        ProposalUpdate(summary="Missing"),
        actor="qa",
    )

    assert missing_requirement is None
    assert missing_proposal is None
    assert VersionHistoryService.list_versions(db_session, "requirement", 999) == []
    assert VersionHistoryService.list_versions(db_session, "proposal", 999) == []
