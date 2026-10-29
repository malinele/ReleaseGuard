"""Tests for local asynchronous workflow approval requests."""
from app.models.project import Project
from app.models.proposal import Proposal, RiskLevel, WorkflowStatus
from app.models.workflow_approval_request import ApprovalRequestStatus
from app.services.workflow_approval_service import WorkflowApprovalService


def _create_project(db_session) -> Project:
    project = Project(name="Approval Project", description="Approval tests")
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
        proposal_id="PROP-APPROVAL-001",
        summary="Approval workflow proposal",
        generated_by="pytest",
        files_expected=[],
        risk_level=RiskLevel.MEDIUM,
        workflow_status=status,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)
    return proposal


def test_request_transition_does_not_change_proposal_status(db_session):
    project = _create_project(db_session)
    proposal = _create_proposal(db_session, project)

    request, message = WorkflowApprovalService.request_transition(
        db_session,
        proposal_id=proposal.id,
        requested_status=WorkflowStatus.CONTEXT_REVIEW,
        requester="requester",
        reason="Needs review",
    )
    db_session.refresh(proposal)

    assert request is not None
    assert message == "Workflow transition approval requested"
    assert request.request_status == ApprovalRequestStatus.PENDING
    assert request.requested_status == WorkflowStatus.CONTEXT_REVIEW
    assert request.requester == "requester"
    assert proposal.workflow_status == WorkflowStatus.DRAFT


def test_approve_request_applies_transition_and_marks_approved(db_session):
    project = _create_project(db_session)
    proposal = _create_proposal(db_session, project)
    request, _ = WorkflowApprovalService.request_transition(
        db_session,
        proposal_id=proposal.id,
        requested_status=WorkflowStatus.CONTEXT_REVIEW,
        requester="requester",
    )

    decided, message = WorkflowApprovalService.approve_request(
        db_session,
        request.id,
        approver="approver",
        decision_reason="Approved",
    )
    db_session.refresh(proposal)

    assert decided is not None
    assert message == "Workflow transition approved"
    assert decided.request_status == ApprovalRequestStatus.APPROVED
    assert decided.approver == "approver"
    assert decided.decided_at is not None
    assert proposal.workflow_status == WorkflowStatus.CONTEXT_REVIEW


def test_reject_request_does_not_change_proposal_status(db_session):
    project = _create_project(db_session)
    proposal = _create_proposal(db_session, project)
    request, _ = WorkflowApprovalService.request_transition(
        db_session,
        proposal_id=proposal.id,
        requested_status=WorkflowStatus.CONTEXT_REVIEW,
        requester="requester",
    )

    decided, message = WorkflowApprovalService.reject_request(
        db_session,
        request.id,
        approver="approver",
        decision_reason="Not enough context",
    )
    db_session.refresh(proposal)

    assert decided is not None
    assert message == "Workflow transition rejected"
    assert decided.request_status == ApprovalRequestStatus.REJECTED
    assert decided.decided_at is not None
    assert proposal.workflow_status == WorkflowStatus.DRAFT


def test_decided_request_cannot_be_decided_again(db_session):
    project = _create_project(db_session)
    proposal = _create_proposal(db_session, project)
    request, _ = WorkflowApprovalService.request_transition(
        db_session,
        proposal_id=proposal.id,
        requested_status=WorkflowStatus.CONTEXT_REVIEW,
        requester="requester",
    )
    WorkflowApprovalService.reject_request(db_session, request.id, approver="approver")

    decided, message = WorkflowApprovalService.approve_request(
        db_session,
        request.id,
        approver="second-approver",
    )
    db_session.refresh(proposal)

    assert decided is None
    assert message == "Approval request already rejected"
    assert proposal.workflow_status == WorkflowStatus.DRAFT


def test_invalid_transition_request_stays_pending_when_approval_fails(db_session):
    project = _create_project(db_session)
    proposal = _create_proposal(db_session, project)
    request, _ = WorkflowApprovalService.request_transition(
        db_session,
        proposal_id=proposal.id,
        requested_status=WorkflowStatus.TEST_REVIEW,
        requester="requester",
    )

    decided, message = WorkflowApprovalService.approve_request(
        db_session,
        request.id,
        approver="approver",
    )
    db_session.refresh(request)
    db_session.refresh(proposal)

    assert decided is None
    assert "Invalid transition" in message
    assert request.request_status == ApprovalRequestStatus.PENDING
    assert request.decided_at is None
    assert proposal.workflow_status == WorkflowStatus.DRAFT


def test_missing_proposal_or_request_returns_clear_message(db_session):
    request, request_message = WorkflowApprovalService.request_transition(
        db_session,
        proposal_id=999,
        requested_status=WorkflowStatus.CONTEXT_REVIEW,
    )
    decided, decision_message = WorkflowApprovalService.approve_request(
        db_session,
        999,
        approver="approver",
    )

    assert request is None
    assert request_message == "Proposal not found"
    assert decided is None
    assert decision_message == "Approval request not found"
