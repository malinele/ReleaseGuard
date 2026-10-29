"""Release readiness API endpoint."""
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
from app.models.user import User
from app.services.workflow_service import WorkflowService
from app.schemas.release_readiness import ReleaseReadinessResponse, ReleaseReadinessItem

router = APIRouter(prefix="/api", tags=["release-readiness"])


def _enforce_release_readiness_read_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce release-readiness:read only when user auth is explicitly required."""
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
            detail="Authentication required for release readiness read",
        )
    if not rbac.user_is_allowed(user, "release-readiness:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for release readiness read",
        )
    return user


@router.get("/release-readiness", response_model=ReleaseReadinessResponse)
def get_release_readiness(
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_release_readiness_read_rbac),
):
    """Get release readiness summary for all proposals."""
    from app.models import Proposal
    
    proposals = db.query(Proposal).all()
    items = []
    release_ready_count = 0
    blocked_count = 0
    
    for proposal in proposals:
        gates_passed, missing_gates = WorkflowService.check_release_gates(db, proposal.id)
        
        item = ReleaseReadinessItem(
            proposal_id=proposal.proposal_id,
            summary=proposal.summary,
            workflow_status=proposal.workflow_status,
            gates_passed=gates_passed,
            missing_gates=missing_gates,
        )
        items.append(item)
        
        if gates_passed:
            release_ready_count += 1
        else:
            blocked_count += 1
    
    return ReleaseReadinessResponse(
        total_proposals=len(proposals),
        release_ready=release_ready_count,
        blocked=blocked_count,
        items=items,
    )
