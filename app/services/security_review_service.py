"""SecurityReview service."""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.security_review import SecurityReview
from app.schemas.security_review import SecurityReviewCreate, SecurityReviewUpdate
from app.services.audit_service import AuditService
from app.models.audit_event import AuditAction


class SecurityReviewService:
    """Service for security review operations."""

    @staticmethod
    def create_security_review(
        db: Session,
        review_data: SecurityReviewCreate,
        actor: Optional[str] = None,
    ) -> SecurityReview:
        """Create a new security review."""
        review = SecurityReview(**review_data.model_dump())
        db.add(review)
        db.commit()
        db.refresh(review)
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.CREATE,
            entity_type="security_review",
            entity_id=review.id,
            actor=actor,
            after_summary=f"Created security review for proposal {review.proposal_id}",
        )
        return review

    @staticmethod
    def get_security_review(db: Session, proposal_id: int) -> Optional[SecurityReview]:
        """Get security review for a proposal."""
        return db.query(SecurityReview).filter(
            SecurityReview.proposal_id == proposal_id
        ).first()

    @staticmethod
    def update_security_review(
        db: Session,
        proposal_id: int,
        review_data: SecurityReviewUpdate,
        actor: Optional[str] = None,
    ) -> Optional[SecurityReview]:
        """Update a security review."""
        review = db.query(SecurityReview).filter(
            SecurityReview.proposal_id == proposal_id
        ).first()
        if not review:
            return None

        before_summary = f"Security review for proposal {proposal_id}"
        update_data = review_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(review, field, value)

        db.commit()
        db.refresh(review)
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.UPDATE,
            entity_type="security_review",
            entity_id=review.id,
            actor=actor,
            before_summary=before_summary,
            after_summary=f"Updated security review for proposal {proposal_id}",
        )
        return review