"""Local user credential service.

This is the KI-001 authentication foundation slice only. It provides local
password hashing and verification primitives without changing request auth,
sessions, tokens, RBAC, API routes, or UI behavior.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User

PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 120_000
SALT_BYTES = 16
USER_ROLES = frozenset({"owner", "admin", "finance", "support", "viewer"})
DEFAULT_USER_ROLE = "viewer"
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_SECONDS = 15 * 60


class UserService:
    """Service for local user credential operations."""

    MAX_FAILED_LOGIN_ATTEMPTS = MAX_FAILED_LOGIN_ATTEMPTS
    ACCOUNT_LOCKOUT_SECONDS = ACCOUNT_LOCKOUT_SECONDS

    @staticmethod
    def hash_password(password: str, *, salt: Optional[bytes] = None) -> str:
        """Hash a plaintext password using stdlib PBKDF2-HMAC-SHA256."""
        if not password:
            raise ValueError("password must not be empty")
        salt = salt if salt is not None else os.urandom(SALT_BYTES)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PASSWORD_HASH_ITERATIONS,
        )
        return (
            f"{PASSWORD_HASH_ALGORITHM}"
            f"${PASSWORD_HASH_ITERATIONS}"
            f"${salt.hex()}"
            f"${digest.hex()}"
        )

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Return True when password matches a stored password hash."""
        try:
            algorithm, iterations_text, salt_hex, expected_hex = password_hash.split("$", 3)
            if algorithm != PASSWORD_HASH_ALGORITHM:
                return False
            iterations = int(iterations_text)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(expected_hex)
        except (TypeError, ValueError):
            return False

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(digest, expected)

    @staticmethod
    def create_user(
        db: Session,
        *,
        username: str,
        password: str,
        display_name: Optional[str] = None,
        role: str = DEFAULT_USER_ROLE,
    ) -> User:
        """Create a local user with a hashed password."""
        normalized_username = username.strip()
        if not normalized_username:
            raise ValueError("username must not be empty")
        if UserService.get_user_by_username(db, normalized_username):
            raise ValueError("username already exists")
        normalized_role = UserService.validate_role(role)

        user = User(
            username=normalized_username,
            password_hash=UserService.hash_password(password),
            display_name=display_name,
            role=normalized_role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """Return a user by username."""
        return db.query(User).filter(User.username == username.strip()).first()

    @staticmethod
    def verify_user_password(db: Session, username: str, password: str) -> bool:
        """Verify a local user's password without exposing the hash."""
        user = UserService.get_user_by_username(db, username)
        if not user or not user.is_active:
            return False
        if UserService.user_is_locked(user):
            return False
        verified = UserService.verify_password(password, user.password_hash)
        if verified:
            UserService.clear_failed_logins(db, user)
        return verified

    @staticmethod
    def user_is_locked(user: User) -> bool:
        """Return True when the user's lockout window is still active."""
        return bool(user.locked_until and user.locked_until > datetime.utcnow())

    @staticmethod
    def record_failed_login(db: Session, user: User) -> User:
        """Increment failed-login count and lock the account at threshold."""
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= UserService.MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(
                seconds=UserService.ACCOUNT_LOCKOUT_SECONDS
            )
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def clear_failed_logins(db: Session, user: User) -> User:
        """Clear failed-login state after successful authentication."""
        if user.failed_login_attempts or user.locked_until is not None:
            user.failed_login_attempts = 0
            user.locked_until = None
            db.commit()
            db.refresh(user)
        return user

    @staticmethod
    def unlock_user(db: Session, user_id: int) -> User:
        """Clear account lockout state for an existing local user."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("user not found")
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def reset_password(db: Session, user_id: int, password: str) -> User:
        """Set a new password hash and clear lockout state for an existing user."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("user not found")
        user.password_hash = UserService.hash_password(password)
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def validate_role(role: str) -> str:
        """Normalize and validate a local user role."""
        normalized_role = (role or "").strip().lower()
        if normalized_role not in USER_ROLES:
            allowed = ", ".join(sorted(USER_ROLES))
            raise ValueError(f"role must be one of: {allowed}")
        return normalized_role

    @staticmethod
    def assign_role(db: Session, user_id: int, role: str) -> User:
        """Assign a valid role to an existing user."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("user not found")
        user.role = UserService.validate_role(role)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def has_role(user: User, *roles: str) -> bool:
        """Return True if user has one of the provided roles."""
        if not roles:
            return False
        allowed_roles = {UserService.validate_role(role) for role in roles}
        return (user.role or "").strip().lower() in allowed_roles
