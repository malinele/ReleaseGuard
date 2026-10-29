"""Version history model for auditable entity updates."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class EntityVersion(Base):
    """Direct version-history row for requirement/proposal updates."""

    __tablename__ = "entity_versions"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    actor = Column(String(100), nullable=True)
    before_summary = Column(Text, nullable=True)
    after_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
