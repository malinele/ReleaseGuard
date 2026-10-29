"""Focused tests for the KI-001 RBAC policy foundation."""
import pytest
from fastapi import HTTPException

from app.models.user import User
from app.rbac import (
    ALLOWED_ROLES,
    POLICY,
    ROLE_ADMIN,
    ROLE_FINANCE,
    ROLE_OWNER,
    ROLE_SUPPORT,
    ROLE_VIEWER,
    allowed_roles_for,
    is_role_allowed,
    require_role,
    user_has_allowed_role,
    user_is_allowed,
)
from app.services.user_service import USER_ROLES, UserService


REQUIRED_ACTIONS = (
    "projects:read",
    "projects:write",
    "requirements:read",
    "requirements:write",
    "proposals:read",
    "proposals:write",
    "audit:read",
    "traceability:read",
    "release-readiness:read",
    "release:decide",
    "admin:manage_users",
)


def test_policy_uses_releaseguard_role_vocabulary():
    """The policy vocabulary must match UserService's accepted roles."""
    assert set(ALLOWED_ROLES) == USER_ROLES


def test_policy_covers_required_actions():
    for action in REQUIRED_ACTIONS:
        assert action in POLICY


def test_policy_only_uses_allowed_roles():
    for roles in POLICY.values():
        assert set(roles).issubset(set(ALLOWED_ROLES))


@pytest.mark.parametrize(
    "action",
    ["projects:read", "requirements:read", "proposals:read", "release-readiness:read"],
)
@pytest.mark.parametrize(
    "role",
    [ROLE_OWNER, ROLE_ADMIN, ROLE_FINANCE, ROLE_SUPPORT, ROLE_VIEWER],
)
def test_read_actions_allow_all_roles(action, role):
    assert is_role_allowed(role, action) is True


def test_write_actions_are_role_restricted():
    assert is_role_allowed(ROLE_OWNER, "proposals:write") is True
    assert is_role_allowed(ROLE_ADMIN, "proposals:write") is True
    assert is_role_allowed(ROLE_FINANCE, "proposals:write") is True
    assert is_role_allowed(ROLE_SUPPORT, "proposals:write") is False
    assert is_role_allowed(ROLE_VIEWER, "proposals:write") is False


def test_release_decision_is_owner_or_admin_only():
    assert is_role_allowed(ROLE_OWNER, "release:decide") is True
    assert is_role_allowed(ROLE_ADMIN, "release:decide") is True
    assert is_role_allowed(ROLE_FINANCE, "release:decide") is False
    assert is_role_allowed(ROLE_SUPPORT, "release:decide") is False
    assert is_role_allowed(ROLE_VIEWER, "release:decide") is False


def test_admin_manage_users_is_owner_or_admin_only():
    assert is_role_allowed(ROLE_OWNER, "admin:manage_users") is True
    assert is_role_allowed(ROLE_ADMIN, "admin:manage_users") is True
    assert is_role_allowed(ROLE_FINANCE, "admin:manage_users") is False
    assert is_role_allowed(ROLE_SUPPORT, "admin:manage_users") is False
    assert is_role_allowed(ROLE_VIEWER, "admin:manage_users") is False


def test_unknown_action_and_empty_role_are_denied():
    assert is_role_allowed(ROLE_ADMIN, "not:a:real:action") is False
    assert is_role_allowed(None, "projects:read") is False
    assert is_role_allowed("", "projects:read") is False


def test_user_helpers_use_existing_user_role_semantics(db_session):
    owner = UserService.create_user(
        db_session,
        username="owner-policy",
        password="secret-password",
        role="owner",
    )
    viewer = UserService.create_user(
        db_session,
        username="viewer-policy",
        password="secret-password",
    )

    assert user_is_allowed(owner, "release:decide") is True
    assert user_is_allowed(viewer, "release:decide") is False
    assert user_is_allowed(viewer, "projects:read") is True
    assert user_has_allowed_role(owner, "admin:manage_users") is True
    assert user_has_allowed_role(viewer, "admin:manage_users") is False


def test_user_helpers_reject_none():
    assert user_is_allowed(None, "projects:read") is False
    assert user_has_allowed_role(None, "projects:read") is False


def test_allowed_roles_for_known_action():
    roles = allowed_roles_for("admin:manage_users")

    assert ROLE_OWNER in roles
    assert ROLE_ADMIN in roles
    assert ROLE_VIEWER not in roles


def test_allowed_roles_for_unknown_action_raises():
    with pytest.raises(KeyError):
        allowed_roles_for("not:a:real:action")


def test_require_role_returns_user_when_role_allowed():
    owner = User(username="owner", role=ROLE_OWNER, is_active=True)
    dependency = require_role("release:decide")

    assert dependency(owner) is owner


def test_require_role_raises_403_when_role_denied():
    viewer = User(username="viewer", role=ROLE_VIEWER, is_active=True)
    dependency = require_role("release:decide")

    with pytest.raises(HTTPException) as excinfo:
        dependency(viewer)

    assert excinfo.value.status_code == 403


def test_require_role_raises_403_for_none_user():
    dependency = require_role("projects:read")

    with pytest.raises(HTTPException) as excinfo:
        dependency(None)

    assert excinfo.value.status_code == 403


def test_require_role_rejects_unknown_action_at_factory_time():
    with pytest.raises(ValueError):
        require_role("not:a:real:action")
