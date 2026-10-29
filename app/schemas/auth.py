"""Authentication API schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    """Username/password login payload."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """Bearer token response returned after successful login."""

    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class CurrentUserResponse(BaseModel):
    """Current authenticated user identity."""

    id: int
    username: str
    display_name: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class LogoutResponse(BaseModel):
    """Logout result."""

    status: str
