"""Requirement service."""
from typing import Optional, List
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.models.requirement import Requirement
from app.schemas.requirement import RequirementCreate, RequirementUpdate
from app.services.audit_service import AuditService
from app.models.audit_event import AuditAction
from app.services.version_history_service import VersionHistoryService


class RequirementService:
    """Service for requirement operations."""

    @staticmethod
    def create_requirement(
        db: Session,
        requirement_data: RequirementCreate,
        actor: Optional[str] = None,
    ) -> Requirement:
        """Create a new requirement."""
        requirement = Requirement(**requirement_data.model_dump())
        db.add(requirement)
        db.commit()
        db.refresh(requirement)
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.CREATE,
            entity_type="requirement",
            entity_id=requirement.id,
            actor=actor,
            after_summary=f"Created requirement: {requirement.requirement_id}",
        )
        return requirement

    @staticmethod
    def get_requirement(db: Session, requirement_id: int) -> Optional[Requirement]:
        """Get a requirement by ID."""
        return db.query(Requirement).filter(Requirement.id == requirement_id).first()

    @staticmethod
    def get_requirements(
        db: Session,
        project_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
        q: Optional[str] = None,
    ) -> List[Requirement]:
        """Get requirements, optionally filtered by project and/or case-insensitive q substring."""
        query = db.query(Requirement)
        if project_id:
            query = query.filter(Requirement.project_id == project_id)
        if q is not None:
            needle = q.strip().lower()
            if needle:
                query = query.filter(
                    or_(
                        func.lower(Requirement.requirement_id).contains(needle),
                        func.lower(Requirement.title).contains(needle),
                        func.lower(Requirement.description).contains(needle),
                    )
                )
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def update_requirement(
        db: Session,
        requirement_id: int,
        requirement_data: RequirementUpdate,
        actor: Optional[str] = None,
    ) -> Optional[Requirement]:
        """Update a requirement."""
        requirement = db.query(Requirement).filter(Requirement.id == requirement_id).first()
        if not requirement:
            return None

        before_summary = (
            f"Requirement {requirement.requirement_id}: "
            f"title={requirement.title!r}, status={requirement.status.value}"
        )
        update_data = requirement_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(requirement, field, value)

        db.commit()
        db.refresh(requirement)
        after_summary = (
            f"Requirement {requirement.requirement_id}: "
            f"title={requirement.title!r}, status={requirement.status.value}"
        )
        VersionHistoryService.record_version(
            db=db,
            entity_type="requirement",
            entity_id=requirement.id,
            actor=actor,
            before_summary=before_summary,
            after_summary=after_summary,
        )
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.UPDATE,
            entity_type="requirement",
            entity_id=requirement.id,
            actor=actor,
            before_summary=before_summary,
            after_summary=after_summary,
        )
        return requirement

    @staticmethod
    def delete_requirement(db: Session, requirement_id: int, actor: Optional[str] = None) -> bool:
        """Delete a requirement."""
        requirement = db.query(Requirement).filter(Requirement.id == requirement_id).first()
        if not requirement:
            return False

        before_summary = f"Deleted requirement: {requirement.requirement_id}"
        db.delete(requirement)
        db.commit()
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.DELETE,
            entity_type="requirement",
            entity_id=requirement_id,
            actor=actor,
            before_summary=before_summary,
        )
        return True
