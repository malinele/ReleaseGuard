"""Tests for local user credential service."""
import pytest

from app.models.user import User
from app.services.user_service import UserService


def test_hash_password_does_not_store_plaintext_and_verifies():
    password_hash = UserService.hash_password("correct horse battery staple")

    assert "correct horse battery staple" not in password_hash
    assert password_hash.startswith("pbkdf2_sha256$")
    assert UserService.verify_password("correct horse battery staple", password_hash)
    assert not UserService.verify_password("wrong password", password_hash)


def test_hash_password_is_salted():
    first = UserService.hash_password("same password")
    second = UserService.hash_password("same password")

    assert first != second
    assert UserService.verify_password("same password", first)
    assert UserService.verify_password("same password", second)


def test_create_user_stores_hash_and_verifies_password(db_session):
    user = UserService.create_user(
        db_session,
        username="alice",
        password="secret-password",
        display_name="Alice",
    )

    assert user.id is not None
    assert user.username == "alice"
    assert user.display_name == "Alice"
    assert user.role == "viewer"
    assert user.is_active is True
    assert user.password_hash != "secret-password"
    assert UserService.verify_user_password(db_session, "alice", "secret-password")
    assert not UserService.verify_user_password(db_session, "alice", "wrong")


def test_create_user_rejects_duplicate_username(db_session):
    UserService.create_user(db_session, username="alice", password="first")

    with pytest.raises(ValueError, match="username already exists"):
        UserService.create_user(db_session, username="alice", password="second")

    assert db_session.query(User).filter(User.username == "alice").count() == 1


def test_missing_or_inactive_user_password_verification_fails(db_session):
    user = UserService.create_user(db_session, username="inactive", password="secret")
    user.is_active = False
    db_session.commit()

    assert not UserService.verify_user_password(db_session, "missing", "secret")
    assert not UserService.verify_user_password(db_session, "inactive", "secret")


def test_empty_username_or_password_rejected(db_session):
    with pytest.raises(ValueError, match="username must not be empty"):
        UserService.create_user(db_session, username="   ", password="secret")

    with pytest.raises(ValueError, match="password must not be empty"):
        UserService.create_user(db_session, username="bob", password="")


def test_create_user_accepts_explicit_valid_role(db_session):
    user = UserService.create_user(
        db_session,
        username="finance-user",
        password="secret-password",
        role="finance",
    )

    assert user.role == "finance"


def test_create_user_normalizes_role(db_session):
    user = UserService.create_user(
        db_session,
        username="support-user",
        password="secret-password",
        role=" Support ",
    )

    assert user.role == "support"


def test_create_user_rejects_invalid_role(db_session):
    with pytest.raises(ValueError, match="role must be one of"):
        UserService.create_user(
            db_session,
            username="invalid-role-user",
            password="secret-password",
            role="superuser",
        )


def test_assign_role_updates_existing_user(db_session):
    user = UserService.create_user(db_session, username="alice-role", password="secret")

    updated = UserService.assign_role(db_session, user.id, "admin")

    assert updated.role == "admin"
    assert db_session.query(User).filter(User.id == user.id).first().role == "admin"


def test_assign_role_rejects_missing_user(db_session):
    with pytest.raises(ValueError, match="user not found"):
        UserService.assign_role(db_session, 9999, "admin")


def test_assign_role_rejects_invalid_role(db_session):
    user = UserService.create_user(db_session, username="invalid-assign", password="secret")

    with pytest.raises(ValueError, match="role must be one of"):
        UserService.assign_role(db_session, user.id, "root")


def test_has_role_checks_user_role(db_session):
    owner = UserService.create_user(
        db_session,
        username="owner-user",
        password="secret-password",
        role="owner",
    )

    assert UserService.has_role(owner, "owner")
    assert UserService.has_role(owner, "admin", "owner")
    assert not UserService.has_role(owner, "viewer", "support")
    assert not UserService.has_role(owner)
