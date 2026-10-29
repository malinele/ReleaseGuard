"""Project service."""
from typing import Optional, List
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.audit_service import AuditService
from app.models.audit_event import AuditAction


class ProjectService:
    """Service for project operations."""

    @staticmethod
    def create_project(db: Session, project_data: ProjectCreate, actor: Optional[str] = None) -> Project:
        """Create a new project."""
        project = Project(**project_data.model_dump())
        db.add(project)
        db.commit()
        db.refresh(project)
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.CREATE,
            entity_type="project",
            entity_id=project.id,
            actor=actor,
            after_summary=f"Created project: {project.name}",
        )
        return project

    @staticmethod
    def get_project(db: Session, project_id: int) -> Optional[Project]:
        """Get a project by ID."""
        return db.query(Project).filter(Project.id == project_id).first()

    @staticmethod
    def get_projects(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        q: Optional[str] = None,
    ) -> List[Project]:
        """Get all projects, optionally filtered by case-insensitive q substring on name/description."""
        query = db.query(Project)
        if q is not None:
            needle = q.strip().lower()
            if needle:
                query = query.filter(
                    or_(
                        func.lower(Project.name).contains(needle),
                        func.lower(Project.description).contains(needle),
                    )
                )
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def update_project(
        db: Session,
        project_id: int,
        project_data: ProjectUpdate,
        actor: Optional[str] = None,
    ) -> Optional[Project]:
        """Update a project."""
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return None

        before_summary = f"Project {project_id}: {project.name}"
        update_data = project_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)

        db.commit()
        db.refresh(project)
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.UPDATE,
            entity_type="project",
            entity_id=project.id,
            actor=actor,
            before_summary=before_summary,
            after_summary=f"Updated project: {project.name}",
        )
        return project

    @staticmethod
    def delete_project(db: Session, project_id: int, actor: Optional[str] = None) -> bool:
        """Delete a project."""
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return False

        before_summary = f"Deleted project: {project.name}"
        db.delete(project)
        db.commit()
        AuditService.create_audit_event(
            db=db,
            action=AuditAction.DELETE,
            entity_type="project",
            entity_id=project_id,
            actor=actor,
            before_summary=before_summary,
        )
        return True