"""ReleaseDecision schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.release_decision import Decision


class ReleaseDecisionBase(BaseModel):
    """Base release decision schema."""
    decision: Decision
    decision_maker: Optional[str] = None
    decision_notes: Optional[str] = None


class ReleaseDecisionCreate(ReleaseDecisionBase):
    """Release decision create schema."""
    proposal_id: int


class ReleaseDecisionUpdate(BaseModel):
    """Release decision update schema."""
    decision: Optional[Decision] = None
    decision_maker: Optional[str] = None
    decision_notes: Optional[str] = None


class ReleaseDecisionResponse(ReleaseDecisionBase):
    """Release decision response schema."""
    id: int
    proposal_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)