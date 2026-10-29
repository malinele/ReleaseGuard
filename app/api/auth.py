"""Authentication endpoints for local ReleaseGuard users."""
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.user_session import UserSession
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LogoutResponse,
    TokenResponse,
)
from app.services.session_service import SessionService
from app.services.user_service import UserService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _extract_bearer_token(authorization: Optional[str]) -> str:
    """Extract a bearer token from the Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization bearer token required",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization bearer token required",
        )
    return token.strip()


def _current_session_and_user(
    db: Session,
    authorization: Optional[str],
) -> Tuple[UserSession, User]:
    """Resolve an active session and user from an Authorization header."""
    token = _extract_bearer_token(authorization)
    session = SessionService.get_session_for_token(db, token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )

    user = (
        db.query(User)
        .filter(
            User.id == session.user_id,
            User.is_active.is_(True),
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive user",
        )
    return session, user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Create a local bearer session for a valid active user."""
    if not UserService.verify_user_password(db, payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    user = UserService.get_user_by_username(db, payload.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    created = SessionService.create_session(db, user_id=user.id)
    return TokenResponse(
        access_token=created.token,
        expires_at=created.session.expires_at,
    )


@router.get("/me", response_model=CurrentUserResponse)
def current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Return the user for the active bearer session."""
    _, user = _current_session_and_user(db, authorization)
    return user


@router.post("/logout", response_model=LogoutResponse)
def logout(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    """Revoke the active bearer session."""
    session, _ = _current_session_and_user(db, authorization)
    SessionService.revoke_session(db, session.id)
    return LogoutResponse(status="logged_out")
