"""Projects API endpoints."""
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
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _enforce_projects_write_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce projects:write only when user auth is explicitly required."""
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
            detail="Authentication required for project write",
        )
    if not rbac.user_is_allowed(user, "projects:write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for project write",
        )
    return user


def _enforce_projects_read_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce projects:read only when user auth is explicitly required."""
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
            detail="Authentication required for project read",
        )
    if not rbac.user_is_allowed(user, "projects:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for project read",
        )
    return user


@router.get("", response_model=List[ProjectResponse])
def get_projects(
    skip: int = 0,
    limit: int = 100,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_projects_read_rbac),
):
    """Get all projects, optionally filtered by case-insensitive q substring on name/description."""
    return ProjectService.get_projects(db, skip=skip, limit=limit, q=q)


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_projects_write_rbac),
):
    """Create a new project."""
    return ProjectService.create_project(db, project_data, actor=actor)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_projects_read_rbac),
):
    """Get a project by ID."""
    project = ProjectService.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_projects_write_rbac),
):
    """Update a project."""
    project = ProjectService.update_project(db, project_id, project_data, actor=actor)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    actor: Optional[str] = Header(None),
    _authorized_user: Optional[User] = Depends(_enforce_projects_write_rbac),
):
    """Delete a project."""
    success = ProjectService.delete_project(db, project_id, actor=actor)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
