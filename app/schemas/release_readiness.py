"""Release readiness API response schemas."""
from typing import List
from pydantic import BaseModel


class ReleaseReadinessItem(BaseModel):
    """Individual proposal release readiness status."""
    proposal_id: str
    summary: str
    workflow_status: str
    gates_passed: bool
    missing_gates: List[str]


class ReleaseReadinessResponse(BaseModel):
    """Response schema for release readiness endpoint."""
    total_proposals: int
    release_ready: int
    blocked: int
    items: List[ReleaseReadinessItem]
