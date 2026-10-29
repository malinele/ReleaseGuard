"""Service for local asynchronous workflow approval requests."""
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.proposal import Proposal, WorkflowStatus
from app.models.workflow_approval_request import (
    ApprovalRequestStatus,
    WorkflowApprovalRequest,
)
from app.services.workflow_service import WorkflowService


class WorkflowApprovalService:
    """Creates and decides local workflow transition approval requests."""

    @staticmethod
    def request_transition(
        db: Session,
        *,
        proposal_id: int,
        requested_status: WorkflowStatus,
        requester: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Tuple[Optional[WorkflowApprovalRequest], str]:
        """Create a pending approval request without changing workflow state."""
        proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
        if not proposal:
            return None, "Proposal not found"

        request = WorkflowApprovalRequest(
            proposal_id=proposal_id,
            requested_status=requested_status,
            request_status=ApprovalRequestStatus.PENDING,
            requester=requester,
            reason=reason,
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        return request, "Workflow transition approval requested"

    @staticmethod
    def approve_request(
        db: Session,
        request_id: int,
        *,
        approver: Optional[str] = None,
        decision_reason: Optional[str] = None,
    ) -> Tuple[Optional[WorkflowApprovalRequest], str]:
        """Approve a pending request and apply the requested workflow transition."""
        request = (
            db.query(WorkflowApprovalRequest)
            .filter(WorkflowApprovalRequest.id == request_id)
            .first()
        )
        if not request:
            return None, "Approval request not found"
        if request.request_status != ApprovalRequestStatus.PENDING:
            return None, f"Approval request already {request.request_status.value}"

        proposal, message = WorkflowService.transition_proposal(
            db,
            request.proposal_id,
            request.requested_status,
            actor=approver,
        )
        if not proposal:
            return None, message

        request.request_status = ApprovalRequestStatus.APPROVED
        request.approver = approver
        request.decision_reason = decision_reason
        request.decided_at = datetime.utcnow()
        db.commit()
        db.refresh(request)
        return request, "Workflow transition approved"

    @staticmethod
    def reject_request(
        db: Session,
        request_id: int,
        *,
        approver: Optional[str] = None,
        decision_reason: Optional[str] = None,
    ) -> Tuple[Optional[WorkflowApprovalRequest], str]:
        """Reject a pending request without changing workflow state."""
        request = (
            db.query(WorkflowApprovalRequest)
            .filter(WorkflowApprovalRequest.id == request_id)
            .first()
        )
        if not request:
            return None, "Approval request not found"
        if request.request_status != ApprovalRequestStatus.PENDING:
            return None, f"Approval request already {request.request_status.value}"

        request.request_status = ApprovalRequestStatus.REJECTED
        request.approver = approver
        request.decision_reason = decision_reason
        request.decided_at = datetime.utcnow()
        db.commit()
        db.refresh(request)
        return request, "Workflow transition rejected"
