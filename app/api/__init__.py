"""API endpoints for ReleaseGuard."""
from app.api.projects import router as projects_router
from app.api.requirements import router as requirements_router
from app.api.proposals import router as proposals_router
from app.api.proposal_requirements import router as proposal_requirements_router
from app.api.test_evidence import router as test_evidence_router
from app.api.security_reviews import router as security_reviews_router
from app.api.release_decisions import router as release_decisions_router
from app.api.audit import router as audit_router
from app.api.traceability import router as traceability_router
from app.api.release_readiness import router as release_readiness_router
from app.api.auth import router as auth_router

__all__ = [
    "projects_router",
    "requirements_router",
    "proposals_router",
    "proposal_requirements_router",
    "test_evidence_router",
    "security_reviews_router",
    "release_decisions_router",
    "audit_router",
    "traceability_router",
    "release_readiness_router",
    "auth_router",
]
