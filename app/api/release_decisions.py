"""Release Decisions API endpoints."""
from __future__ import annotations

from typing import Optional

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
from app.schemas.release_decision import ReleaseDecisionCreate, ReleaseDecisionResponse
from app.services.release_decision_service import ReleaseDecisionService

router = APIRouter(prefix="/api/proposals/{proposal_id}/release-decision", tags=["release_decisions"])


def _enforce_release_decide_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce release:decide only when user auth is explicitly required."""
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
            detail="Authentication required for release decision",
        )
    if not rbac.user_is_allowed(user, "release:decide"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for release decision",
        )
    return user


def _enforce_release_decisions_read_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce release_decisions:read only when user auth is explicitly required."""
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
            detail="Authentication required for release decision read",
        )
    if not rbac.user_is_allowed(user, "release_decisions:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for release decision read",
        )
    return user


@router.get("", response_model=ReleaseDecisionResponse)
def get_release_decision(
    proposal_id: int,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_release_decisions_read_rbac),
):
    """Get release decision for a proposal."""
    decision = ReleaseDecisionService.get_release_decision(db, proposal_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Release decision not found")
    return decision


@router.post("", response_model=ReleaseDecisionResponse, status_code=201)
def create_release_decision(
    proposal_id: int,
    decision_data: ReleaseDecisionCreate,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_release_decide_rbac),
):
    """Create a release decision for a proposal."""
    if decision_data.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="proposal_id mismatch")
    return ReleaseDecisionService.create_release_decision(db, decision_data, actor=actor)
