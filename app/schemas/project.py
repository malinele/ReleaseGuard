"""Project schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ProjectBase(BaseModel):
    """Base project schema."""
    name: str
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Project create schema."""
    pass


class ProjectUpdate(BaseModel):
    """Project update schema."""
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(ProjectBase):
    """Project response schema."""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)