"""AuditEvent model."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
from app.database import Base


class AuditAction(str, enum.Enum):
    """Audit actions."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class AuditEvent(Base):
    """AuditEvent model."""

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    actor = Column(String(255), nullable=True, index=True)
    action = Column(Enum(AuditAction), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    before_summary = Column(Text, nullable=True)
    after_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
