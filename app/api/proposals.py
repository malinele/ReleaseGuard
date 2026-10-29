"""Proposals API endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
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
from app.schemas.proposal import ProposalCreate, ProposalResponse, ProposalUpdate, TransitionRequest
from app.services.proposal_service import ProposalService
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


def _enforce_proposals_write_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce proposals:write only when user auth is explicitly required."""
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
            detail="Authentication required for proposal write",
        )
    if not rbac.user_is_allowed(user, "proposals:write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for proposal write",
        )
    return user


def _enforce_proposals_read_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce proposals:read only when user auth is explicitly required."""
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
            detail="Authentication required for proposal read",
        )
    if not rbac.user_is_allowed(user, "proposals:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for proposal read",
        )
    return user


@router.get("", response_model=List[ProposalResponse])
def get_proposals(
    project_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_proposals_read_rbac),
):
    """Get all proposals, optionally filtered by project."""
    return ProposalService.get_proposals(db, project_id=project_id, skip=skip, limit=limit)


@router.post("", response_model=ProposalResponse, status_code=201)
def create_proposal(
    proposal_data: ProposalCreate,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_proposals_write_rbac),
):
    """Create a new proposal."""
    return ProposalService.create_proposal(db, proposal_data, actor=actor)


@router.get("/{proposal_id}", response_model=ProposalResponse)
def get_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_proposals_read_rbac),
):
    """Get a proposal by ID."""
    proposal = ProposalService.get_proposal(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


@router.put("/{proposal_id}", response_model=ProposalResponse)
def update_proposal(
    proposal_id: int,
    proposal_data: ProposalUpdate,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_proposals_write_rbac),
):
    """Update a proposal."""
    proposal = ProposalService.update_proposal(db, proposal_id, proposal_data, actor=actor)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


@router.delete("/{proposal_id}", status_code=204)
def delete_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_proposals_write_rbac),
):
    """Delete a proposal."""
    success = ProposalService.delete_proposal(db, proposal_id, actor=actor)
    if not success:
        raise HTTPException(status_code=404, detail="Proposal not found")


@router.post("/{proposal_id}/transition")
def transition_proposal(
    proposal_id: int,
    transition_data: TransitionRequest,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_proposals_write_rbac),
):
    """Transition a proposal to a new workflow status."""
    proposal, message = WorkflowService.transition_proposal(
        db, proposal_id, transition_data.target_status, actor=transition_data.actor
    )
    if not proposal:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message, "proposal": proposal}
