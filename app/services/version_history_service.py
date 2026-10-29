"""Service for direct requirement/proposal version history."""
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entity_version import EntityVersion


class VersionHistoryService:
    """Records direct version history for auditable entity updates."""

    @staticmethod
    def next_version_number(db: Session, entity_type: str, entity_id: int) -> int:
        """Return the next monotonically increasing version number."""
        current = (
            db.query(func.max(EntityVersion.version_number))
            .filter(
                EntityVersion.entity_type == entity_type,
                EntityVersion.entity_id == entity_id,
            )
            .scalar()
        )
        return int(current or 0) + 1

    @staticmethod
    def record_version(
        db: Session,
        *,
        entity_type: str,
        entity_id: int,
        before_summary: str,
        after_summary: str,
        actor: Optional[str] = None,
    ) -> EntityVersion:
        """Persist one version-history row for an entity update."""
        version = EntityVersion(
            entity_type=entity_type,
            entity_id=entity_id,
            version_number=VersionHistoryService.next_version_number(
                db,
                entity_type,
                entity_id,
            ),
            actor=actor,
            before_summary=before_summary,
            after_summary=after_summary,
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        return version

    @staticmethod
    def list_versions(db: Session, entity_type: str, entity_id: int) -> list[EntityVersion]:
        """List direct version-history rows for an entity."""
        return (
            db.query(EntityVersion)
            .filter(
                EntityVersion.entity_type == entity_type,
                EntityVersion.entity_id == entity_id,
            )
            .order_by(EntityVersion.version_number.asc())
            .all()
        )
