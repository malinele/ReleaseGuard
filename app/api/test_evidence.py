"""Test Evidence API endpoints."""
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
from app.schemas.test_evidence import TestEvidenceCreate, TestEvidenceUpdate, TestEvidenceResponse
from app.services.test_evidence_service import TestEvidenceService

router = APIRouter(prefix="/api", tags=["test_evidence"])


def _enforce_test_evidence_write_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce test_evidence:write only when user auth is explicitly required."""
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
            detail="Authentication required for test evidence write",
        )
    if not rbac.user_is_allowed(user, "test_evidence:write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for test evidence write",
        )
    return user


def _enforce_test_evidence_read_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce test_evidence:read only when user auth is explicitly required."""
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
            detail="Authentication required for test evidence read",
        )
    if not rbac.user_is_allowed(user, "test_evidence:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for test evidence read",
        )
    return user


@router.get("/proposals/{proposal_id}/test-evidence", response_model=List[TestEvidenceResponse])
def get_test_evidence_for_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_test_evidence_read_rbac),
):
    """Get all test evidence for a proposal."""
    return TestEvidenceService.get_test_evidence_for_proposal(db, proposal_id)


@router.post("/proposals/{proposal_id}/test-evidence", response_model=TestEvidenceResponse, status_code=201)
def create_test_evidence(
    proposal_id: int,
    evidence_data: TestEvidenceCreate,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_test_evidence_write_rbac),
):
    """Create test evidence for a proposal."""
    if evidence_data.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="proposal_id mismatch")
    return TestEvidenceService.create_test_evidence(db, evidence_data, actor=actor)


@router.put("/test-evidence/{evidence_id}", response_model=TestEvidenceResponse)
def update_test_evidence(
    evidence_id: int,
    evidence_data: TestEvidenceUpdate,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_test_evidence_write_rbac),
):
    """Update test evidence."""
    evidence = TestEvidenceService.update_test_evidence(db, evidence_id, evidence_data, actor=actor)
    if not evidence:
        raise HTTPException(status_code=404, detail="Test evidence not found")
    return evidence


@router.delete("/test-evidence/{evidence_id}", status_code=204)
def delete_test_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_test_evidence_write_rbac),
):
    """Delete test evidence."""
    success = TestEvidenceService.delete_test_evidence(db, evidence_id, actor=actor)
    if not success:
        raise HTTPException(status_code=404, detail="Test evidence not found")

__test__ = False
