"""TestEvidence schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator
from app.models.test_evidence import TestType, TestResult


def _validate_command_or_procedure(value):
    """Reject empty or whitespace-only command_or_procedure values.

    Skips validation for ``None`` so partial update payloads remain legal,
    and returns the original value unchanged when valid.
    """
    if value is None:
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError("command_or_procedure must not be empty or whitespace")
    return value


class TestEvidenceBase(BaseModel):
    """Base test evidence schema."""
    test_type: TestType
    command_or_procedure: str
    result: TestResult
    evidence_notes: Optional[str] = None


class TestEvidenceCreate(TestEvidenceBase):
    """Test evidence create schema."""
    proposal_id: int

    @field_validator("command_or_procedure")
    @classmethod
    def _validate_command(cls, value: str) -> str:
        return _validate_command_or_procedure(value)


class TestEvidenceUpdate(BaseModel):
    """Test evidence update schema."""
    test_type: Optional[TestType] = None
    command_or_procedure: Optional[str] = None
    result: Optional[TestResult] = None
    evidence_notes: Optional[str] = None

    @field_validator("command_or_procedure")
    @classmethod
    def _validate_command(cls, value):
        return _validate_command_or_procedure(value)


class TestEvidenceResponse(TestEvidenceBase):
    """Test evidence response schema."""
    id: int
    proposal_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

__test__ = False
