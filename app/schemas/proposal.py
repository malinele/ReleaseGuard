"""Proposal schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.models.proposal import WorkflowStatus, RiskLevel


class ProposalBase(BaseModel):
    """Base proposal schema."""
    proposal_id: str
    summary: str
    generated_by: Optional[str] = None
    files_expected: List[str] = []
    risk_level: RiskLevel = RiskLevel.MEDIUM
    rationale: Optional[str] = None


class ProposalCreate(ProposalBase):
    """Proposal create schema."""
    project_id: int


class ProposalUpdate(BaseModel):
    """Proposal update schema."""
    summary: Optional[str] = None
    generated_by: Optional[str] = None
    files_expected: Optional[List[str]] = None
    risk_level: Optional[RiskLevel] = None
    rationale: Optional[str] = None
    workflow_status: Optional[WorkflowStatus] = None


class ProposalResponse(ProposalBase):
    """Proposal response schema."""
    id: int
    project_id: int
    workflow_status: WorkflowStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransitionRequest(BaseModel):
    """Workflow transition request."""
    target_status: WorkflowStatus
    actor: Optional[str] = None