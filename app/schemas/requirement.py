"""Requirement schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.requirement import Priority, RequirementStatus


class RequirementBase(BaseModel):
    """Base requirement schema."""
    requirement_id: str
    title: str
    description: Optional[str] = None
    priority: Priority = Priority.MEDIUM
    acceptance_criteria: Optional[str] = None
    status: RequirementStatus = RequirementStatus.ACTIVE


class RequirementCreate(RequirementBase):
    """Requirement create schema."""
    project_id: int


class RequirementUpdate(BaseModel):
    """Requirement update schema."""
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Priority] = None
    acceptance_criteria: Optional[str] = None
    status: Optional[RequirementStatus] = None


class RequirementResponse(RequirementBase):
    """Requirement response schema."""
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)