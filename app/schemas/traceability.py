"""Traceability schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from app.schemas.project import ProjectResponse
from app.schemas.requirement import RequirementResponse
from app.schemas.proposal import ProposalResponse
from app.schemas.test_evidence import TestEvidenceResponse
from app.schemas.security_review import SecurityReviewResponse
from app.schemas.release_decision import ReleaseDecisionResponse


class ProposalTraceabilityResponse(BaseModel):
    """Traceability for a single proposal."""
    project: ProjectResponse
    requirements: List[RequirementResponse]
    proposal: ProposalResponse
    test_evidence: List[TestEvidenceResponse]
    security_review: Optional[SecurityReviewResponse]
    release_decision: Optional[ReleaseDecisionResponse]


class TraceabilityResponse(BaseModel):
    """Full traceability response."""
    projects: List[ProjectResponse]
    requirements: List[RequirementResponse]
    proposals: List[ProposalResponse]
    test_evidence: List[TestEvidenceResponse]
    security_reviews: List[SecurityReviewResponse]
    release_decisions: List[ReleaseDecisionResponse]