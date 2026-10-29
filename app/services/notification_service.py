"""Local notification hook service.

This module intentionally keeps notifications in process memory. It provides a
deterministic hook point for workflow transitions without adding email,
webhooks, background workers, network calls, or database schema changes.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, ClassVar, List, Optional

from app.models.proposal import WorkflowStatus


@dataclass(frozen=True)
class NotificationEvent:
    """A deterministic notification payload emitted by service-layer hooks."""

    event_type: str
    entity_type: str
    entity_id: int
    actor: Optional[str]
    before_status: str
    after_status: str
    message: str
    created_at: datetime

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-friendly representation for tests and future APIs."""
        payload = asdict(self)
        payload["created_at"] = self.created_at.isoformat()
        return payload


class NotificationService:
    """In-memory notification outbox for local workflow hooks."""

    _events: ClassVar[List[NotificationEvent]] = []

    @classmethod
    def record_workflow_transition(
        cls,
        *,
        proposal_id: int,
        proposal_ref: str,
        from_status: WorkflowStatus,
        to_status: WorkflowStatus,
        actor: Optional[str] = None,
    ) -> NotificationEvent:
        """Record a workflow transition notification in the local outbox."""
        event = NotificationEvent(
            event_type="workflow_transition",
            entity_type="proposal",
            entity_id=proposal_id,
            actor=actor,
            before_status=from_status.value,
            after_status=to_status.value,
            message=(
                f"Proposal {proposal_ref} transitioned "
                f"from {from_status.value} to {to_status.value}"
            ),
            created_at=datetime.utcnow(),
        )
        cls._events.append(event)
        return event

    @classmethod
    def list_events(cls) -> List[NotificationEvent]:
        """Return a snapshot of recorded notification events."""
        return list(cls._events)

    @classmethod
    def clear(cls) -> None:
        """Clear the in-memory outbox between tests or local runs."""
        cls._events.clear()
