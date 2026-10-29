"""SecurityReview model."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, UniqueConstraint
from app.database import Base


class SecurityReviewStatus(str, enum.Enum):
    """Security review status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    WAIVED = "waived"


class SecurityReview(Base):
    """SecurityReview model."""

    __tablename__ = "security_reviews"

    id = Column(Integer, primary_key=True, index=True)
    proposal_id = Column(Integer, ForeignKey("proposals.id"), nullable=False, unique=True)
    status = Column(Enum(SecurityReviewStatus), default=SecurityReviewStatus.PENDING)
    reviewer = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    risk_acceptance_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)