"""SecurityReview schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.security_review import SecurityReviewStatus


class SecurityReviewBase(BaseModel):
    """Base security review schema."""
    status: SecurityReviewStatus = SecurityReviewStatus.PENDING
    reviewer: Optional[str] = None
    notes: Optional[str] = None
    risk_acceptance_reason: Optional[str] = None


class SecurityReviewCreate(SecurityReviewBase):
    """Security review create schema."""
    proposal_id: int


class SecurityReviewUpdate(BaseModel):
    """Security review update schema."""
    status: Optional[SecurityReviewStatus] = None
    reviewer: Optional[str] = None
    notes: Optional[str] = None
    risk_acceptance_reason: Optional[str] = None


class SecurityReviewResponse(SecurityReviewBase):
    """Security review response schema."""
    id: int
    proposal_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)