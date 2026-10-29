"""Requirement model."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from app.database import Base


class Priority(str, enum.Enum):
    """Priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RequirementStatus(str, enum.Enum):
    """Requirement status."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SATISFIED = "satisfied"


class Requirement(Base):
    """Requirement model."""

    __tablename__ = "requirements"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    requirement_id = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Enum(Priority), default=Priority.MEDIUM)
    acceptance_criteria = Column(Text, nullable=True)
    status = Column(Enum(RequirementStatus), default=RequirementStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)