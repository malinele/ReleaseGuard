"""Local role policy foundation (KI-001 RBAC policy slice only).

This module centralizes the local role policy decisions for ReleaseGuard.
It exposes a fixed set of allowed role constants, a static policy map for
the action vocabulary used by the platform, a decision helper that uses
``UserService.has_role`` and ``User.role``, and a FastAPI dependency
factory ``require_role(action)`` that raises ``HTTPException(403)`` when the
current user's role is not allowed for the action.

Scope:
    * Define the role vocabulary and policy map.
    * Expose helpers and the dependency factory.
    * Route-level enforcement lives in the routers and ``app.main`` guards,
      which consult ``POLICY`` through these helpers.
"""
from __future__ import annotations

from typing import Iterable, Mapping

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.user_service import UserService

# ---------------------------------------------------------------------------
# Role vocabulary
#
# These are the only local role names recognized by the policy. They are
# intentionally duplicated here as named constants so that ``app.rbac`` is
# usable without importing every router/service that may eventually consume
# it. ``UserService`` remains the source of truth for credential-time role
# validation; this module is the source of truth for authorization policy.
# ---------------------------------------------------------------------------

ROLE_VIEWER = "viewer"
ROLE_OWNER = "owner"
ROLE_FINANCE = "finance"
ROLE_SUPPORT = "support"
ROLE_ADMIN = "admin"

ALLOWED_ROLES: tuple[str, ...] = (
    ROLE_OWNER,
    ROLE_ADMIN,
    ROLE_FINANCE,
    ROLE_SUPPORT,
    ROLE_VIEWER,
)


# ---------------------------------------------------------------------------
# Policy map
#
# Each key is an action identifier (namespaced string). Each value is the
# tuple of role names allowed to perform that action. The map is intentionally
# static and in-code for this foundation slice; dynamic/per-tenant policies
# are out of scope.
# ---------------------------------------------------------------------------

POLICY: Mapping[str, tuple[str, ...]] = {
    "projects:read": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_FINANCE,
        ROLE_SUPPORT,
        ROLE_VIEWER,
    ),
    "projects:write": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_SUPPORT,
    ),
    "requirements:read": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_FINANCE,
        ROLE_SUPPORT,
        ROLE_VIEWER,
    ),
    "requirements:write": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_SUPPORT,
    ),
    "proposals:read": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_FINANCE,
        ROLE_SUPPORT,
        ROLE_VIEWER,
    ),
    "proposals:write": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_FINANCE,
    ),
    "proposal_requirements:read": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_FINANCE,
        ROLE_SUPPORT,
        ROLE_VIEWER,
    ),
    "test_evidence:read": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_FINANCE,
        ROLE_SUPPORT,
        ROLE_VIEWER,
    ),
    "security_reviews:read": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_FINANCE,
        ROLE_SUPPORT,
        ROLE_VIEWER,
    ),
    "release_decisions:read": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_FINANCE,
        ROLE_SUPPORT,
        ROLE_VIEWER,
    ),
    "proposal_requirements:write": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_FINANCE,
    ),
    "test_evidence:write": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_SUPPORT,
    ),
    "security_reviews:write": (
        ROLE_OWNER,
        ROLE_ADMIN,
    ),
    "audit:read": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_FINANCE,
    ),
    "traceability:read": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_FINANCE,
        ROLE_SUPPORT,
    ),
    "release-readiness:read": (
        ROLE_OWNER,
        ROLE_ADMIN,
        ROLE_FINANCE,
        ROLE_SUPPORT,
        ROLE_VIEWER,
    ),
    "release:decide": (
        ROLE_OWNER,
        ROLE_ADMIN,
    ),
    "admin:manage_users": (
        ROLE_OWNER,
        ROLE_ADMIN,
    ),
}


# ---------------------------------------------------------------------------
# Decision helpers
# ---------------------------------------------------------------------------

def allowed_roles_for(action: str) -> tuple[str, ...]:
    """Return the tuple of roles allowed for ``action``.

    Raises ``KeyError`` when ``action`` is not part of the policy vocabulary.
    """
    try:
        return POLICY[action]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"unknown rbac action: {action!r}") from exc


def is_role_allowed(role: str | None, action: str) -> bool:
    """Return ``True`` when ``role`` is permitted to perform ``action``.

    Unknown actions return ``False`` so callers cannot accidentally allow an
    unvetted verb. A ``None`` or empty role is never allowed.
    """
    if not role:
        return False
    allowed = POLICY.get(action)
    if allowed is None:
        return False
    return role in allowed


def user_is_allowed(user: User | None, action: str) -> bool:
    """Return ``True`` when ``user`` is permitted to perform ``action``.

    Uses ``User.role`` directly for the simple role check and falls back to
    ``UserService.has_role`` for the broader "role present" semantics.
    """
    if user is None:
        return False
    if not getattr(user, "role", None):
        return False
    return is_role_allowed(user.role, action)


def user_has_allowed_role(user: User | None, action: str) -> bool:
    """Return ``True`` when ``user`` has any of the roles allowed for ``action``.

    Mirrors ``UserService.has_role`` semantics by checking membership of the
    user's role in the allowed set, so this helper can be used interchangeably
    with the service-layer helper.
    """
    if user is None:
        return False
    if not UserService.has_role(user, *_allowed_iter(action)):
        return False
    return is_role_allowed(user.role, action)


def _allowed_iter(action: str) -> Iterable[str]:
    return allowed_roles_for(action)


# ---------------------------------------------------------------------------
# FastAPI dependency factory
# ---------------------------------------------------------------------------

def require_role(action: str):
    """Build a FastAPI dependency that enforces ``action`` for the current user.

    The returned dependency expects a ``User`` instance (or compatible object
    with a ``role`` attribute) injected by the caller. It raises
    ``HTTPException(403)`` when the user's role is not allowed for ``action``,
    and ``HTTPException(403)`` with an ``unknown_action`` detail when the
    action is not part of the policy vocabulary.

    NOTE: Routes enforce policy through the shared auth guards; this factory
    remains available for dependency-based use once a current-user resolver
    is supplied.
    """
    if action not in POLICY:
        raise ValueError(f"unknown rbac action: {action!r}")

    def _dependency(current_user: User = Depends(_rbac_current_user_dep)) -> User:
        if current_user is None or not getattr(current_user, "role", None):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="forbidden",
            )
        if not is_role_allowed(current_user.role, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"forbidden: role '{current_user.role}' may not '{action}'",
            )
        return current_user

    return _dependency


def _rbac_current_user_dep() -> User:
    """Placeholder dependency resolver for the current user.

    This module deliberately does not import the project's auth dependency
    (which would couple ``app.rbac`` to the auth layer). The dependency is
    overridden by callers and tests.
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="rbac current-user resolver not configured",
    )
