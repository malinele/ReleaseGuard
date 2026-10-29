"""Security Reviews API endpoints."""
from typing import Optional
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
from app.schemas.security_review import SecurityReviewCreate, SecurityReviewResponse
from app.services.security_review_service import SecurityReviewService

router = APIRouter(prefix="/api/proposals/{proposal_id}/security-review", tags=["security_reviews"])


def _enforce_security_reviews_write_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce security_reviews:write only when user auth is explicitly required."""
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
            detail="Authentication required for security review write",
        )
    if not rbac.user_is_allowed(user, "security_reviews:write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for security review write",
        )
    return user


def _enforce_security_reviews_read_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce security_reviews:read only when user auth is explicitly required."""
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
            detail="Authentication required for security review read",
        )
    if not rbac.user_is_allowed(user, "security_reviews:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for security review read",
        )
    return user


@router.get("", response_model=SecurityReviewResponse)
def get_security_review(
    proposal_id: int,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_security_reviews_read_rbac),
):
    """Get security review for a proposal."""
    review = SecurityReviewService.get_security_review(db, proposal_id)
    if not review:
        raise HTTPException(status_code=404, detail="Security review not found")
    return review


@router.post("", response_model=SecurityReviewResponse, status_code=201)
def create_security_review(
    proposal_id: int,
    review_data: SecurityReviewCreate,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_security_reviews_write_rbac),
):
    """Create a security review for a proposal."""
    if review_data.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="proposal_id mismatch")
    return SecurityReviewService.create_security_review(db, review_data, actor=actor)