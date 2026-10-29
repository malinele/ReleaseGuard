"""Workflow approval request model."""
import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text

from app.database import Base
from app.models.proposal import WorkflowStatus


class ApprovalRequestStatus(str, enum.Enum):
    """Decision status for a workflow approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class WorkflowApprovalRequest(Base):
    """Local asynchronous approval request for proposal workflow transitions."""

    __tablename__ = "workflow_approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    proposal_id = Column(Integer, ForeignKey("proposals.id"), nullable=False, index=True)
    requested_status = Column(Enum(WorkflowStatus), nullable=False)
    request_status = Column(
        Enum(ApprovalRequestStatus),
        default=ApprovalRequestStatus.PENDING,
        nullable=False,
        index=True,
    )
    requester = Column(String(100), nullable=True)
    approver = Column(String(100), nullable=True)
    reason = Column(Text, nullable=True)
    decision_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    decided_at = Column(DateTime, nullable=True)
