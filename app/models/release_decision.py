"""ReleaseDecision model."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, UniqueConstraint
from app.database import Base


class Decision(str, enum.Enum):
    """Release decisions."""
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    CONDITIONAL = "conditional"


class ReleaseDecision(Base):
    """ReleaseDecision model."""

    __tablename__ = "release_decisions"

    id = Column(Integer, primary_key=True, index=True)
    proposal_id = Column(Integer, ForeignKey("proposals.id"), nullable=False, unique=True)
    decision = Column(Enum(Decision), nullable=False)
    decision_maker = Column(String(255), nullable=True)
    decision_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)