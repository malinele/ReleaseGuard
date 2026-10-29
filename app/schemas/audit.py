"""Audit schemas."""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.audit_event import AuditAction


class AuditEventResponse(BaseModel):
    """Audit event response schema."""
    id: int
    timestamp: datetime
    actor: Optional[str]
    action: AuditAction
    entity_type: str
    entity_id: Optional[int]
    before_summary: Optional[str]
    after_summary: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditExportFilters(BaseModel):
    """Filters applied to audit export."""
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    actor: Optional[str] = None
    limit: int = 100


class AuditExportSummary(BaseModel):
    """Summary statistics for audit export."""
    by_action: Dict[str, int]
    by_entity_type: Dict[str, int]
    actors: Dict[str, int]


class AuditExportResponse(BaseModel):
    """Audit export response schema."""
    total_events: int
    filters: AuditExportFilters
    summary: AuditExportSummary
    events: List[AuditEventResponse]
