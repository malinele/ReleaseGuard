"""Proposal model."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON
from app.database import Base


class WorkflowStatus(str, enum.Enum):
    """Workflow states."""
    DRAFT = "draft"
    CONTEXT_REVIEW = "context_review"
    IMPLEMENTATION = "implementation"
    TEST_REVIEW = "test_review"
    SECURITY_REVIEW = "security_review"
    RELEASE_READY = "release_ready"
    RELEASED = "released"


class RiskLevel(str, enum.Enum):
    """Risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Proposal(Base):
    """Proposal model."""

    __tablename__ = "proposals"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    proposal_id = Column(String(50), nullable=False)
    summary = Column(String(500), nullable=False)
    generated_by = Column(String(255), nullable=True)
    files_expected = Column(JSON, default=list)
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.MEDIUM)
    rationale = Column(Text, nullable=True)
    workflow_status = Column(Enum(WorkflowStatus), default=WorkflowStatus.DRAFT)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)