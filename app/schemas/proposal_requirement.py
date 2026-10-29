"""ProposalRequirement schemas."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ProposalRequirementBase(BaseModel):
    """Base proposal requirement schema."""
    requirement_id: int


class ProposalRequirementCreate(ProposalRequirementBase):
    """Proposal requirement create schema."""
    proposal_id: int


class ProposalRequirementResponse(ProposalRequirementBase):
    """Proposal requirement response schema."""
    id: int
    proposal_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)