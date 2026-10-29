"""ReleaseGuard opt-in API access protection for /api routes.

This module implements the KI-001 strengthening mitigation. It is intentionally
small: read auth-related environment variables at request time and preserve
local development behavior unless protection is explicitly configured.

If no auth env var is set, all requests are allowed unchanged. /health,
server-rendered UI routes, and /api/auth endpoints are not gated by the shared
API guard.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.session_service import SessionService

PROTECTED_API_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})
API_PATH_PREFIX = "/api"
AUTH_API_PATH_PREFIX = "/api/auth"
WRITE_TOKEN_ENV = "RELEASEGUARD_WRITE_TOKEN"
WRITE_TOKEN_HEADER = "X-ReleaseGuard-Token"
USER_AUTH_ENV = "RELEASEGUARD_REQUIRE_USER_AUTH"
RELEASEGUARD_ENV = "RELEASEGUARD_ENV"


def _configured_token() -> Optional[str]:
    """Return the configured write token, or None when it is unset/blank."""
    token = os.environ.get(WRITE_TOKEN_ENV)
    if token is None:
        return None
    token = token.strip()
    return token or None


def _production_mode() -> bool:
    """Return True when ReleaseGuard is explicitly running in production mode."""
    value = os.environ.get(RELEASEGUARD_ENV, "").strip().lower()
    return value in {"prod", "production"}


def _user_auth_required() -> bool:
    """Return True when user-session auth is explicitly required.

    Production mode is fail-closed: protected API/UI routes require either a
    valid shared token override or a valid user session. Local-dev behavior
    remains unchanged when RELEASEGUARD_ENV is unset.
    """
    value = os.environ.get(USER_AUTH_ENV, "").strip().lower()
    return value in {"1", "true", "yes", "on"} or _production_mode()


def _request_path(request: Request) -> str:
    """Return the request path, preferring url.path with a safe fallback."""
    try:
        return request.url.path
    except Exception:
        return getattr(request, "path", "") or ""


def is_protected_path(request: Request) -> bool:
    """Return True if this request should be subject to API access protection.

    Every method on /api paths is protected (GET, POST, PUT, PATCH, DELETE)
    when auth protection is configured. /health, non-/api paths, and /api/auth
    routes are always excluded from this shared guard.
    """
    method = (request.method or "").upper()
    if method not in PROTECTED_API_METHODS:
        return False
    path = _request_path(request)
    return path.startswith(API_PATH_PREFIX) and not path.startswith(AUTH_API_PATH_PREFIX)


def require_releaseguard_write_token(request: Request) -> None:
    """FastAPI dependency that enforces the opt-in write-token guard.

    Apply this only to routes that pass :func:`is_protected_path`. When the
    env var is unset or blank this dependency is a no-op so local-dev
    behavior is preserved. When set, mismatched or missing tokens raise 401.
    """
    expected = _configured_token()
    if expected is None:
        return None

    provided = request.headers.get(WRITE_TOKEN_HEADER)
    if provided is None or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-ReleaseGuard-Token header",
        )
    return None


def check_releaseguard_write_token(request: Request) -> bool:
    """Return True if the request is allowed through the guard.

    Useful for callers that prefer a boolean check (e.g. a small
    guard dependency) rather than raising inside a dependency. Returns
    True when no token is configured or when the header matches.
    """
    expected = _configured_token()
    if expected is None:
        return True
    provided = request.headers.get(WRITE_TOKEN_HEADER)
    return provided is not None and provided == expected


def _extract_bearer_token(request: Request) -> Optional[str]:
    """Return Authorization bearer token text when present and syntactically valid."""
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def check_releaseguard_user_session(request: Request, db: Session) -> bool:
    """Return True when the request has a valid active user session token."""
    return get_releaseguard_user_session(request, db) is not None


def get_releaseguard_user_session(request: Request, db: Session) -> Optional[User]:
    """Return the active user for a valid bearer session, or None."""
    token = _extract_bearer_token(request)
    if not token:
        return None
    session = SessionService.get_session_for_token(db, token)
    if not session:
        return None
    return (
        db.query(User)
        .filter(
            User.id == session.user_id,
            User.is_active.is_(True),
        )
        .first()
    )


def require_releaseguard_api_access(request: Request, db: Session) -> None:
    """Enforce configured API access protection for non-auth /api routes.

    Compatibility rules:
    - If the shared token is configured and matches, allow.
    - If user auth is explicitly required, allow a valid bearer session.
    - If neither shared token nor user auth is configured, allow local-dev use.
    """
    if _configured_token() is not None and check_releaseguard_write_token(request):
        return None

    if _user_auth_required() and check_releaseguard_user_session(request, db):
        return None

    if _configured_token() is None and not _user_auth_required():
        return None

    detail = "Missing or invalid API authentication"
    if _user_auth_required():
        detail = "Missing or invalid bearer session"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
    )
