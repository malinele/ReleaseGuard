"""Traceability API endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import rbac
from app.auth import (
    WRITE_TOKEN_HEADER,
    _configured_token,
    _user_auth_required,
    get_releaseguard_user_session,
)
from app.database import get_db
from app.schemas.traceability import TraceabilityResponse, ProposalTraceabilityResponse
from app.schemas.project import ProjectResponse
from app.models.user import User
from app.models.proposal import Proposal
from app.models.requirement import Requirement
from app.models.test_evidence import TestEvidence
from app.models.security_review import SecurityReview
from app.models.release_decision import ReleaseDecision
from app.models.project import Project

router = APIRouter(prefix="/api/traceability", tags=["traceability"])


def _enforce_traceability_read_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce traceability:read only when user auth is explicitly required."""
    if not _user_auth_required():
        return None

    expected = _configured_token()
    provided = request.headers.get(WRITE_TOKEN_HEADER)
    if expected and provided == expected:
        return None

    user = get_releaseguard_user_session(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for traceability read",
        )
    if not rbac.user_is_allowed(user, "traceability:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for traceability read",
        )
    return user


@router.get("", response_model=TraceabilityResponse)
def get_traceability(
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_traceability_read_rbac),
):
    """Get full traceability matrix."""
    projects = db.query(Project).all()
    requirements = db.query(Requirement).all()
    proposals = db.query(Proposal).all()
    test_evidence = db.query(TestEvidence).all()
    security_reviews = db.query(SecurityReview).all()
    release_decisions = db.query(ReleaseDecision).all()

    return TraceabilityResponse(
        projects=[ProjectResponse.model_validate(p) for p in projects],
        requirements=requirements,
        proposals=proposals,
        test_evidence=test_evidence,
        security_reviews=security_reviews,
        release_decisions=release_decisions,
    )


@router.get("/proposal/{proposal_id}", response_model=ProposalTraceabilityResponse)
def get_proposal_traceability(
    proposal_id: int,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_traceability_read_rbac),
):
    """Get traceability for a single proposal."""
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    project = db.query(Project).filter(Project.id == proposal.project_id).first()

    from app.models.proposal_requirement import ProposalRequirement
    linked_reqs = db.query(ProposalRequirement).filter(
        ProposalRequirement.proposal_id == proposal_id
    ).all()
    requirement_ids = [lr.requirement_id for lr in linked_reqs]
    requirements = db.query(Requirement).filter(Requirement.id.in_(requirement_ids)).all() if requirement_ids else []

    test_evidence = db.query(TestEvidence).filter(TestEvidence.proposal_id == proposal_id).all()
    security_review = db.query(SecurityReview).filter(SecurityReview.proposal_id == proposal_id).first()
    release_decision = db.query(ReleaseDecision).filter(ReleaseDecision.proposal_id == proposal_id).first()

    return ProposalTraceabilityResponse(
        project=ProjectResponse.model_validate(project),
        requirements=requirements,
        proposal=proposal,
        test_evidence=test_evidence,
        security_review=security_review,
        release_decision=release_decision,
    )
