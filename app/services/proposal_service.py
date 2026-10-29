"""Proposal service."""
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from app.models.proposal import Proposal
from app.models.proposal_requirement import ProposalRequirement
from app.schemas.proposal import ProposalCreate, ProposalUpdate
from app.services.audit_service import AuditService
from app.models.audit_event import AuditAction
from app.services.version_history_service import VersionHistoryService


class ProposalService:
    """Service for proposal operations."""

    @staticmethod
    def create_proposal(
        db: Session,
        proposal_data: ProposalCreate,
        actor: Optional[str] = None,
    ) -> Proposal:
        """Create a new proposal."""
        proposal = Proposal(**proposal_data.model_dump())
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.CREATE,
            entity_type="proposal",
            entity_id=proposal.id,
            actor=actor,
            after_summary=f"Created proposal: {proposal.proposal_id}",
        )
        return proposal

    @staticmethod
    def get_proposal(db: Session, proposal_id: int) -> Optional[Proposal]:
        """Get a proposal by ID."""
        return db.query(Proposal).filter(Proposal.id == proposal_id).first()

    @staticmethod
    def get_proposals(
        db: Session,
        project_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Proposal]:
        """Get proposals, optionally filtered by project."""
        query = db.query(Proposal)
        if project_id:
            query = query.filter(Proposal.project_id == project_id)
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def update_proposal(
        db: Session,
        proposal_id: int,
        proposal_data: ProposalUpdate,
        actor: Optional[str] = None,
    ) -> Optional[Proposal]:
        """Update a proposal."""
        proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
        if not proposal:
            return None

        before_summary = (
            f"Proposal {proposal.proposal_id}: "
            f"summary={proposal.summary!r}, workflow_status={proposal.workflow_status.value}"
        )
        update_data = proposal_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(proposal, field, value)

        db.commit()
        db.refresh(proposal)
        after_summary = (
            f"Proposal {proposal.proposal_id}: "
            f"summary={proposal.summary!r}, workflow_status={proposal.workflow_status.value}"
        )
        VersionHistoryService.record_version(
            db=db,
            entity_type="proposal",
            entity_id=proposal.id,
            actor=actor,
            before_summary=before_summary,
            after_summary=after_summary,
        )
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.UPDATE,
            entity_type="proposal",
            entity_id=proposal.id,
            actor=actor,
            before_summary=before_summary,
            after_summary=after_summary,
        )
        return proposal

    @staticmethod
    def delete_proposal(db: Session, proposal_id: int, actor: Optional[str] = None) -> bool:
        """Delete a proposal."""
        proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
        if not proposal:
            return False

        before_summary = f"Deleted proposal: {proposal.proposal_id}"
        db.delete(proposal)
        db.commit()
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.DELETE,
            entity_type="proposal",
            entity_id=proposal_id,
            actor=actor,
            before_summary=before_summary,
        )
        return True

    @staticmethod
    def link_requirement(
        db: Session,
        proposal_id: int,
        requirement_id: int,
        actor: Optional[str] = None,
    ) -> ProposalRequirement:
        """Link a requirement to a proposal."""
        link = ProposalRequirement(proposal_id=proposal_id, requirement_id=requirement_id)
        db.add(link)
        db.commit()
        db.refresh(link)
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.CREATE,
            entity_type="proposal_requirement",
            entity_id=link.id,
            actor=actor,
            after_summary=f"Linked requirement {requirement_id} to proposal {proposal_id}",
        )
        return link

    @staticmethod
    def unlink_requirement(
        db: Session,
        proposal_id: int,
        requirement_id: int,
        actor: Optional[str] = None,
    ) -> bool:
        """Unlink a requirement from a proposal."""
        link = db.query(ProposalRequirement).filter(
            ProposalRequirement.proposal_id == proposal_id,
            ProposalRequirement.requirement_id == requirement_id,
        ).first()
        if not link:
            return False

        db.delete(link)
        db.commit()
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.DELETE,
            entity_type="proposal_requirement",
            entity_id=link.id,
            actor=actor,
            before_summary=f"Unlinked requirement {requirement_id} from proposal {proposal_id}",
        )
        return True

    @staticmethod
    def get_linked_requirements(db: Session, proposal_id: int) -> List[ProposalRequirement]:
        """Get all requirements linked to a proposal."""
        return db.query(ProposalRequirement).filter(
            ProposalRequirement.proposal_id == proposal_id
        ).all()
