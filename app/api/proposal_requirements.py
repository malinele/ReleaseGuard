"""Proposal Requirements API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session
from app import rbac
from app.auth import (
    WRITE_TOKEN_HEADER,
    _configured_token,
    _user_auth_required,
    get_releaseguard_user_session,
)
from app.database import get_db
from app.models.user import User
from app.schemas.proposal_requirement import ProposalRequirementCreate, ProposalRequirementResponse
from app.services.proposal_service import ProposalService

router = APIRouter(prefix="/api/proposals/{proposal_id}/requirements", tags=["proposal_requirements"])


def _enforce_proposal_requirements_write_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce proposal_requirements:write only when user auth is explicitly required."""
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
            detail="Authentication required for proposal requirement write",
        )
    if not rbac.user_is_allowed(user, "proposal_requirements:write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for proposal requirement write",
        )
    return user


def _enforce_proposal_requirements_read_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce proposal_requirements:read only when user auth is explicitly required."""
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
            detail="Authentication required for proposal requirement read",
        )
    if not rbac.user_is_allowed(user, "proposal_requirements:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for proposal requirement read",
        )
    return user


@router.get("", response_model=List[ProposalRequirementResponse])
def get_proposal_requirements(
    proposal_id: int,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_proposal_requirements_read_rbac),
):
    """Get all requirements linked to a proposal."""
    return ProposalService.get_linked_requirements(db, proposal_id)


@router.post("", response_model=ProposalRequirementResponse, status_code=201)
def link_requirement(
    proposal_id: int,
    link_data: ProposalRequirementCreate,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_proposal_requirements_write_rbac),
):
    """Link a requirement to a proposal."""
    if link_data.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="proposal_id mismatch")
    return ProposalService.link_requirement(db, proposal_id, link_data.requirement_id, actor=actor)


@router.delete("/{req_id}", status_code=204)
def unlink_requirement(
    proposal_id: int,
    req_id: int,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_proposal_requirements_write_rbac),
):
    """Unlink a requirement from a proposal."""
    success = ProposalService.unlink_requirement(db, proposal_id, req_id, actor=actor)
    if not success:
        raise HTTPException(status_code=404, detail="Requirement link not found")
