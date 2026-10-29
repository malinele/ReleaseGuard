"""ReleaseGuard FastAPI Application."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app import __version__
from app.database import get_db, init_db
from app.auth import is_protected_path, require_releaseguard_api_access
from app.api import (
    projects_router,
    requirements_router,
    proposals_router,
    proposal_requirements_router,
    test_evidence_router,
    security_reviews_router,
    release_decisions_router,
    audit_router,
    traceability_router,
    release_readiness_router,
    auth_router,
)
from app.ui.routes import router as ui_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup/shutdown events."""
    init_db()
    yield


app = FastAPI(
    title="ReleaseGuard",
    description="Release governance and approval workflow management",
    version=__version__,
    lifespan=lifespan,
)


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach production-safe response headers to every HTTP response.

    Adds ``X-Frame-Options: DENY`` to prevent clickjacking via framing and
    ``X-Content-Type-Options: nosniff`` to prevent MIME-type sniffing. The
    middleware applies uniformly to API, UI, and error responses without
    touching route logic, auth, or database behavior.
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response


app.add_middleware(_SecurityHeadersMiddleware)


def _releaseguard_write_guard(request: Request, db: Session = Depends(get_db)):
    """Single guard dependency that protects configured /api routes."""
    if is_protected_path(request):
        return require_releaseguard_api_access(request, db)
    return None


# Include routers. Mutating /api routes share the opt-in write-token guard.
app.include_router(auth_router)
app.include_router(release_readiness_router, dependencies=[Depends(_releaseguard_write_guard)])
app.include_router(projects_router, dependencies=[Depends(_releaseguard_write_guard)])
app.include_router(requirements_router, dependencies=[Depends(_releaseguard_write_guard)])
app.include_router(proposals_router, dependencies=[Depends(_releaseguard_write_guard)])
app.include_router(proposal_requirements_router, dependencies=[Depends(_releaseguard_write_guard)])
app.include_router(test_evidence_router, dependencies=[Depends(_releaseguard_write_guard)])
app.include_router(security_reviews_router, dependencies=[Depends(_releaseguard_write_guard)])
app.include_router(release_decisions_router, dependencies=[Depends(_releaseguard_write_guard)])
app.include_router(audit_router, dependencies=[Depends(_releaseguard_write_guard)])
app.include_router(traceability_router, dependencies=[Depends(_releaseguard_write_guard)])

# UI router is server-rendered HTML; each route is gated per-route by
# `_enforce_ui_auth` (app/ui/routes.py) when RELEASEGUARD_REQUIRE_USER_AUTH=true.
app.include_router(ui_router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": __version__}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
