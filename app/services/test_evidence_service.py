"""TestEvidence service."""
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.test_evidence import TestEvidence
from app.schemas.test_evidence import TestEvidenceCreate, TestEvidenceUpdate
from app.services.audit_service import AuditService
from app.models.audit_event import AuditAction


class TestEvidenceService:
    """Service for test evidence operations."""

    @staticmethod
    def create_test_evidence(
        db: Session,
        evidence_data: TestEvidenceCreate,
        actor: Optional[str] = None,
    ) -> TestEvidence:
        """Create new test evidence."""
        evidence = TestEvidence(**evidence_data.model_dump())
        db.add(evidence)
        db.commit()
        db.refresh(evidence)
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.CREATE,
            entity_type="test_evidence",
            entity_id=evidence.id,
            actor=actor,
            after_summary=f"Created test evidence for proposal {evidence.proposal_id}",
        )
        return evidence

    @staticmethod
    def get_test_evidence(db: Session, evidence_id: int) -> Optional[TestEvidence]:
        """Get test evidence by ID."""
        return db.query(TestEvidence).filter(TestEvidence.id == evidence_id).first()

    @staticmethod
    def get_test_evidence_for_proposal(
        db: Session,
        proposal_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[TestEvidence]:
        """Get all test evidence for a proposal."""
        return db.query(TestEvidence).filter(
            TestEvidence.proposal_id == proposal_id
        ).offset(skip).limit(limit).all()

    @staticmethod
    def update_test_evidence(
        db: Session,
        evidence_id: int,
        evidence_data: TestEvidenceUpdate,
        actor: Optional[str] = None,
    ) -> Optional[TestEvidence]:
        """Update test evidence."""
        evidence = db.query(TestEvidence).filter(TestEvidence.id == evidence_id).first()
        if not evidence:
            return None

        before_summary = f"Test evidence {evidence_id}"
        update_data = evidence_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(evidence, field, value)

        db.commit()
        db.refresh(evidence)
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.UPDATE,
            entity_type="test_evidence",
            entity_id=evidence.id,
            actor=actor,
            before_summary=before_summary,
            after_summary=f"Updated test evidence for proposal {evidence.proposal_id}",
        )
        return evidence

    @staticmethod
    def delete_test_evidence(db: Session, evidence_id: int, actor: Optional[str] = None) -> bool:
        """Delete test evidence."""
        evidence = db.query(TestEvidence).filter(TestEvidence.id == evidence_id).first()
        if not evidence:
            return False

        before_summary = f"Deleted test evidence {evidence_id}"
        db.delete(evidence)
        db.commit()
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.DELETE,
            entity_type="test_evidence",
            entity_id=evidence_id,
            actor=actor,
            before_summary=before_summary,
        )
        return True

__test__ = False
