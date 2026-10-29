"""ProposalRequirement junction model."""
from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from app.database import Base


class ProposalRequirement(Base):
    """ProposalRequirement junction table."""

    __tablename__ = "proposal_requirements"

    id = Column(Integer, primary_key=True, index=True)
    proposal_id = Column(Integer, ForeignKey("proposals.id"), nullable=False)
    requirement_id = Column(Integer, ForeignKey("requirements.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)