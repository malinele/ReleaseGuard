"""Requirements API endpoints."""
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
from app.schemas.requirement import RequirementCreate, RequirementResponse, RequirementUpdate
from app.services.requirement_service import RequirementService

router = APIRouter(prefix="/api/requirements", tags=["requirements"])


def _enforce_requirements_write_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce requirements:write only when user auth is explicitly required."""
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
            detail="Authentication required for requirement write",
        )
    if not rbac.user_is_allowed(user, "requirements:write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for requirement write",
        )
    return user


def _enforce_requirements_read_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce requirements:read only when user auth is explicitly required."""
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
            detail="Authentication required for requirement read",
        )
    if not rbac.user_is_allowed(user, "requirements:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for requirement read",
        )
    return user


@router.get("", response_model=List[RequirementResponse])
def get_requirements(
    project_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_requirements_read_rbac),
):
    """Get all requirements, optionally filtered by project and/or case-insensitive q substring."""
    return RequirementService.get_requirements(db, project_id=project_id, skip=skip, limit=limit, q=q)


@router.post("", response_model=RequirementResponse, status_code=201)
def create_requirement(
    requirement_data: RequirementCreate,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_requirements_write_rbac),
):
    """Create a new requirement."""
    return RequirementService.create_requirement(db, requirement_data, actor=actor)


@router.get("/{requirement_id}", response_model=RequirementResponse)
def get_requirement(
    requirement_id: int,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_requirements_read_rbac),
):
    """Get a requirement by ID."""
    requirement = RequirementService.get_requirement(db, requirement_id)
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return requirement


@router.put("/{requirement_id}", response_model=RequirementResponse)
def update_requirement(
    requirement_id: int,
    requirement_data: RequirementUpdate,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_requirements_write_rbac),
):
    """Update a requirement."""
    requirement = RequirementService.update_requirement(db, requirement_id, requirement_data, actor=actor)
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return requirement


@router.delete("/{requirement_id}", status_code=204)
def delete_requirement(
    requirement_id: int,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_requirements_write_rbac),
):
    """Delete a requirement."""
    success = RequirementService.delete_requirement(db, requirement_id, actor=actor)
    if not success:
        raise HTTPException(status_code=404, detail="Requirement not found")
