"""TestEvidence model."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from app.database import Base


class TestType(str, enum.Enum):
    """Test types."""
    UNIT = "unit"
    INTEGRATION = "integration"
    SYSTEM = "system"
    MANUAL = "manual"
    AUTOMATED = "automated"


class TestResult(str, enum.Enum):
    """Test results."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    INCONCLUSIVE = "inconclusive"


class TestEvidence(Base):
    """TestEvidence model."""

    __tablename__ = "test_evidence"

    id = Column(Integer, primary_key=True, index=True)
    proposal_id = Column(Integer, ForeignKey("proposals.id"), nullable=False)
    test_type = Column(Enum(TestType), nullable=False)
    command_or_procedure = Column(Text, nullable=False)
    result = Column(Enum(TestResult), nullable=False)
    evidence_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

__test__ = False
