"""Tests for local workflow notification hooks."""
from app.models.project import Project
from app.models.proposal import Proposal, RiskLevel, WorkflowStatus
from app.services.notification_service import NotificationService
from app.services.workflow_service import WorkflowService


def _create_project(db_session) -> Project:
    project = Project(name="Notification Project", description="Local hook tests")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def _create_proposal(
    db_session,
    project: Project,
    *,
    status: WorkflowStatus = WorkflowStatus.DRAFT,
) -> Proposal:
    proposal = Proposal(
        project_id=project.id,
        proposal_id="PROP-NOTIFY-001",
        summary="Notification hook proposal",
        generated_by="pytest",
        files_expected=[],
        risk_level=RiskLevel.MEDIUM,
        workflow_status=status,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)
    return proposal


def setup_function():
    NotificationService.clear()


def teardown_function():
    NotificationService.clear()


def test_successful_transition_records_one_notification(db_session):
    project = _create_project(db_session)
    proposal = _create_proposal(db_session, project)

    transitioned, message = WorkflowService.transition_proposal(
        db_session,
        proposal.id,
        WorkflowStatus.CONTEXT_REVIEW,
        actor="qa",
    )

    assert transitioned is not None
    assert "Successfully transitioned" in message
    events = NotificationService.list_events()
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "workflow_transition"
    assert event.entity_type == "proposal"
    assert event.entity_id == proposal.id
    assert event.actor == "qa"
    assert event.before_status == "draft"
    assert event.after_status == "context_review"
    assert "PROP-NOTIFY-001" in event.message


def test_invalid_transition_records_no_notification(db_session):
    project = _create_project(db_session)
    proposal = _create_proposal(db_session, project)

    transitioned, message = WorkflowService.transition_proposal(
        db_session,
        proposal.id,
        WorkflowStatus.TEST_REVIEW,
        actor="qa",
    )

    assert transitioned is None
    assert "Invalid transition" in message
    assert NotificationService.list_events() == []


def test_gate_failure_records_no_notification(db_session):
    project = _create_project(db_session)
    proposal = _create_proposal(
        db_session,
        project,
        status=WorkflowStatus.SECURITY_REVIEW,
    )

    transitioned, message = WorkflowService.transition_proposal(
        db_session,
        proposal.id,
        WorkflowStatus.RELEASE_READY,
        actor="qa",
    )

    assert transitioned is None
    assert "Gate" in message
    assert NotificationService.list_events() == []


def test_notification_event_model_dump_is_json_friendly(db_session):
    project = _create_project(db_session)
    proposal = _create_proposal(db_session, project)

    WorkflowService.transition_proposal(
        db_session,
        proposal.id,
        WorkflowStatus.CONTEXT_REVIEW,
        actor=None,
    )

    payload = NotificationService.list_events()[0].model_dump()
    assert payload["event_type"] == "workflow_transition"
    assert payload["entity_type"] == "proposal"
    assert payload["actor"] is None
    assert payload["created_at"]
