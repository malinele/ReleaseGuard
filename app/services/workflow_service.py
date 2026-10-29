"""Workflow service for managing proposal state transitions."""
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from app.models.proposal import Proposal, WorkflowStatus
from app.models.proposal_requirement import ProposalRequirement
from app.models.test_evidence import TestEvidence
from app.models.security_review import SecurityReview, SecurityReviewStatus
from app.models.release_decision import ReleaseDecision
from app.services.audit_service import AuditService
from app.models.audit_event import AuditAction
from app.services.notification_service import NotificationService


# Define valid transitions
VALID_TRANSITIONS = {
    WorkflowStatus.DRAFT: [WorkflowStatus.CONTEXT_REVIEW],
    WorkflowStatus.CONTEXT_REVIEW: [WorkflowStatus.IMPLEMENTATION],
    WorkflowStatus.IMPLEMENTATION: [WorkflowStatus.TEST_REVIEW],
    WorkflowStatus.TEST_REVIEW: [WorkflowStatus.SECURITY_REVIEW],
    WorkflowStatus.SECURITY_REVIEW: [WorkflowStatus.RELEASE_READY],
    WorkflowStatus.RELEASE_READY: [WorkflowStatus.RELEASED],
    WorkflowStatus.RELEASED: [],
}


class WorkflowService:
    """Service for managing workflow state transitions."""

    @staticmethod
    def get_valid_transitions(current_status: WorkflowStatus) -> List[WorkflowStatus]:
        """Get valid target statuses from current status."""
        return VALID_TRANSITIONS.get(current_status, [])

    @staticmethod
    def check_release_gates(db: Session, proposal_id: int) -> Tuple[bool, List[str]]:
        """
        Check if all release gates are satisfied.

        Release Gates:
        1. At least one ProposalRequirement linked
        2. At least one TestEvidence exists
        3. Security review passed OR (waived with reason)
        4. ReleaseDecision exists
        """
        gates_passed = True
        failures = []

        # Gate 1: At least one ProposalRequirement linked
        linked_reqs = db.query(ProposalRequirement).filter(
            ProposalRequirement.proposal_id == proposal_id
        ).count()
        if linked_reqs < 1:
            gates_passed = False
            failures.append("Gate 1 failed: No requirements linked to proposal")

        # Gate 2: At least one TestEvidence exists
        test_evidence = db.query(TestEvidence).filter(
            TestEvidence.proposal_id == proposal_id
        ).count()
        if test_evidence < 1:
            gates_passed = False
            failures.append("Gate 2 failed: No test evidence attached")

        # Gate 3: Security review passed OR (waived with reason)
        security_review = db.query(SecurityReview).filter(
            SecurityReview.proposal_id == proposal_id
        ).first()
        if not security_review:
            gates_passed = False
            failures.append("Gate 3 failed: No security review exists")
        elif security_review.status not in [SecurityReviewStatus.PASSED, SecurityReviewStatus.WAIVED]:
            gates_passed = False
            failures.append("Gate 3 failed: Security review not passed or waived")
        elif security_review.status == SecurityReviewStatus.WAIVED and not security_review.risk_acceptance_reason:
            gates_passed = False
            failures.append("Gate 3 failed: Security review waived but no risk acceptance reason")

        # Gate 4: ReleaseDecision exists
        release_decision = db.query(ReleaseDecision).filter(
            ReleaseDecision.proposal_id == proposal_id
        ).first()
        if not release_decision:
            gates_passed = False
            failures.append("Gate 4 failed: No release decision exists")

        return gates_passed, failures

    @staticmethod
    def transition_proposal(
        db: Session,
        proposal_id: int,
        target_status: WorkflowStatus,
        actor: Optional[str] = None,
    ) -> Tuple[Optional[Proposal], str]:
        """
        Transition a proposal to a new workflow status.

        Returns:
            Tuple of (proposal, message)
        """
        proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
        if not proposal:
            return None, "Proposal not found"

        current_status = proposal.workflow_status
        valid_targets = VALID_TRANSITIONS.get(current_status, [])

        if target_status not in valid_targets:
            return None, f"Invalid transition from {current_status.value} to {target_status.value}"

        # Check release gates before security_review -> release_ready
        if current_status == WorkflowStatus.SECURITY_REVIEW and target_status == WorkflowStatus.RELEASE_READY:
            gates_passed, failures = WorkflowService.check_release_gates(db, proposal_id)
            if not gates_passed:
                return None, "; ".join(failures)

        before_summary = f"Proposal {proposal.proposal_id}: {current_status.value}"
        proposal.workflow_status = target_status
        db.commit()
        db.refresh(proposal)
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.UPDATE,
            entity_type="proposal",
            entity_id=proposal.id,
            actor=actor,
            before_summary=before_summary,
            after_summary=f"Transitioned proposal to: {target_status.value}",
        )
        NotificationService.record_workflow_transition(
            proposal_id=proposal.id,
            proposal_ref=proposal.proposal_id,
            from_status=current_status,
            to_status=target_status,
            actor=actor,
        )
        return proposal, f"Successfully transitioned from {current_status.value} to {target_status.value}"
