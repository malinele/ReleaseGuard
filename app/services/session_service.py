"""Local user session service.

This is a KI-001 foundation slice only. It creates and verifies local bearer
tokens without wiring them into request authentication.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_session import UserSession

DEFAULT_SESSION_TTL_SECONDS = 60 * 60 * 8


@dataclass(frozen=True)
class CreatedSession:
    """Return value for session creation.

    The raw token is returned once to the caller; only its hash is persisted.
    """

    session: UserSession
    token: str


class SessionService:
    """Service for local bearer session tokens."""

    @staticmethod
    def hash_token(token: str) -> str:
        """Return a deterministic SHA-256 hash for a bearer token."""
        if not token:
            raise ValueError("token must not be empty")
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def create_session(
        db: Session,
        *,
        user_id: int,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
    ) -> CreatedSession:
        """Create a local session and return the raw token once."""
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise ValueError("active user not found")

        token = secrets.token_urlsafe(32)
        session = UserSession(
            user_id=user_id,
            token_hash=SessionService.hash_token(token),
            expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
            is_active=True,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return CreatedSession(session=session, token=token)

    @staticmethod
    def get_session_for_token(db: Session, token: str) -> Optional[UserSession]:
        """Return the active, unexpired session for a raw token."""
        token_hash = SessionService.hash_token(token)
        session = (
            db.query(UserSession)
            .filter(
                UserSession.token_hash == token_hash,
                UserSession.is_active.is_(True),
            )
            .first()
        )
        if not session:
            return None
        if session.revoked_at is not None:
            return None
        if session.expires_at <= datetime.utcnow():
            return None
        return session

    @staticmethod
    def verify_token(db: Session, token: str) -> bool:
        """Return True if token maps to an active, unexpired session."""
        return SessionService.get_session_for_token(db, token) is not None

    @staticmethod
    def revoke_session(db: Session, session_id: int) -> bool:
        """Revoke an active session."""
        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if not session:
            return False
        if not session.is_active:
            return False
        session.is_active = False
        session.revoked_at = datetime.utcnow()
        db.commit()
        return True
