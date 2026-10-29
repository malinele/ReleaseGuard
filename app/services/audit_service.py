"""Audit service for creating audit events."""
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.audit_event import AuditEvent, AuditAction


class AuditService:
    """Service for creating audit events."""

    @staticmethod
    def create_audit_event(
        db: Session,
        action: AuditAction,
        entity_type: str,
        entity_id: int,
        actor: Optional[str] = None,
        before_summary: Optional[str] = None,
        after_summary: Optional[str] = None,
    ) -> AuditEvent:
        """Create an audit event."""
        audit_event = AuditEvent(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_summary=before_summary,
            after_summary=after_summary,
        )
        db.add(audit_event)
        db.commit()
        db.refresh(audit_event)
        return audit_event

    @staticmethod
    def get_audit_events(
        db: Session,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get audit events with optional filtering."""
        query = db.query(AuditEvent)
        if entity_type:
            query = query.filter(AuditEvent.entity_type == entity_type)
        if entity_id:
            query = query.filter(AuditEvent.entity_id == entity_id)
        return query.order_by(AuditEvent.timestamp.desc()).limit(limit).all()

    @staticmethod
    def get_audit_event(db: Session, audit_id: int) -> Optional[AuditEvent]:
        """Get a single audit event by ID."""
        return db.query(AuditEvent).filter(AuditEvent.id == audit_id).first()