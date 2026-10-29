"""Audit API endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
from app.schemas.audit import (
    AuditEventResponse,
    AuditExportFilters,
    AuditExportResponse,
    AuditExportSummary,
)
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _enforce_audit_read_rbac(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Enforce audit:read only when user auth is explicitly required."""
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
            detail="Authentication required for audit read",
        )
    if not rbac.user_is_allowed(user, "audit:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role not permitted for audit read",
        )
    return user


@router.get("", response_model=List[AuditEventResponse])
def get_audit_events(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[int] = Query(None),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_audit_read_rbac),
):
    """Get audit events with optional filtering."""
    return AuditService.get_audit_events(db, entity_type=entity_type, entity_id=entity_id, limit=limit)


@router.get("/export", response_model=AuditExportResponse)
def get_audit_export(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[int] = Query(None, description="Filter by entity ID"),
    actor: Optional[str] = Query(None, description="Filter by actor"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of events to return"),
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_audit_read_rbac),
):
    """Export audit events with filtering and summary statistics.

    Returns a readonly export of audit events including:
    - total_events: Total count of returned events
    - filters: The filters that were applied
    - summary: Aggregated statistics by action, entity_type, and actors
    - events: The list of audit events
    """
    # Get events from service
    events = AuditService.get_audit_events(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit
    )

    # Filter by actor in memory if specified (service doesn't support actor filtering)
    if actor:
        events = [e for e in events if e.actor == actor]

    # Build summary statistics
    by_action: dict = {}
    by_entity_type: dict = {}
    actors: dict = {}

    for event in events:
        # Count by action
        action_key = event.action.value if hasattr(event.action, 'value') else str(event.action)
        by_action[action_key] = by_action.get(action_key, 0) + 1

        # Count by entity_type
        by_entity_type[event.entity_type] = by_entity_type.get(event.entity_type, 0) + 1

        # Count by actor
        if event.actor:
            actors[event.actor] = actors.get(event.actor, 0) + 1

    return AuditExportResponse(
        total_events=len(events),
        filters=AuditExportFilters(
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            limit=limit
        ),
        summary=AuditExportSummary(
            by_action=by_action,
            by_entity_type=by_entity_type,
            actors=actors
        ),
        events=events
    )


@router.get("/{audit_id}", response_model=AuditEventResponse)
def get_audit_event(
    audit_id: int,
    db: Session = Depends(get_db),
    _authorized_user: Optional[User] = Depends(_enforce_audit_read_rbac),
):
    """Get a single audit event by ID."""
    event = AuditService.get_audit_event(db, audit_id)
    if not event:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return event
