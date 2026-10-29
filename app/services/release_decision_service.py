"""ReleaseDecision service."""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.release_decision import ReleaseDecision
from app.schemas.release_decision import ReleaseDecisionCreate, ReleaseDecisionUpdate
from app.services.audit_service import AuditService
from app.models.audit_event import AuditAction


class ReleaseDecisionService:
    """Service for release decision operations."""

    @staticmethod
    def create_release_decision(
        db: Session,
        decision_data: ReleaseDecisionCreate,
        actor: Optional[str] = None,
    ) -> ReleaseDecision:
        """Create a new release decision."""
        decision = ReleaseDecision(**decision_data.model_dump())
        db.add(decision)
        db.commit()
        db.refresh(decision)
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.CREATE,
            entity_type="release_decision",
            entity_id=decision.id,
            actor=actor,
            after_summary=f"Created release decision for proposal {decision.proposal_id}",
        )
        return decision

    @staticmethod
    def get_release_decision(db: Session, proposal_id: int) -> Optional[ReleaseDecision]:
        """Get release decision for a proposal."""
        return db.query(ReleaseDecision).filter(
            ReleaseDecision.proposal_id == proposal_id
        ).first()

    @staticmethod
    def update_release_decision(
        db: Session,
        proposal_id: int,
        decision_data: ReleaseDecisionUpdate,
        actor: Optional[str] = None,
    ) -> Optional[ReleaseDecision]:
        """Update a release decision."""
        decision = db.query(ReleaseDecision).filter(
            ReleaseDecision.proposal_id == proposal_id
        ).first()
        if not decision:
            return None

        before_summary = f"Release decision for proposal {proposal_id}"
        update_data = decision_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(decision, field, value)

        db.commit()
        db.refresh(decision)
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.UPDATE,
            entity_type="release_decision",
            entity_id=decision.id,
            actor=actor,
            before_summary=before_summary,
            after_summary=f"Updated release decision for proposal {proposal_id}",
        )
        return decision