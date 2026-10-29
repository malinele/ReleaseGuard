"""Tests for local user session service."""
from datetime import datetime, timedelta

import pytest

from app.models.user_session import UserSession
from app.services.session_service import SessionService
from app.services.user_service import UserService


def _create_user(db_session, username="alice"):
    return UserService.create_user(
        db_session,
        username=username,
        password="secret-password",
    )


def test_create_session_returns_raw_token_but_stores_only_hash(db_session):
    user = _create_user(db_session)

    created = SessionService.create_session(db_session, user_id=user.id)

    assert created.token
    assert created.session.id is not None
    assert created.session.token_hash
    assert created.token not in created.session.token_hash
    assert created.session.token_hash == SessionService.hash_token(created.token)
    assert db_session.query(UserSession).count() == 1


def test_verify_token_accepts_current_session_and_rejects_wrong_token(db_session):
    user = _create_user(db_session)
    created = SessionService.create_session(db_session, user_id=user.id)

    assert SessionService.verify_token(db_session, created.token)
    assert not SessionService.verify_token(db_session, "wrong-token")


def test_expired_session_is_not_verified(db_session):
    user = _create_user(db_session)
    created = SessionService.create_session(db_session, user_id=user.id)
    created.session.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()

    assert not SessionService.verify_token(db_session, created.token)
    assert SessionService.get_session_for_token(db_session, created.token) is None


def test_revoke_session_disables_token(db_session):
    user = _create_user(db_session)
    created = SessionService.create_session(db_session, user_id=user.id)

    assert SessionService.revoke_session(db_session, created.session.id)

    db_session.refresh(created.session)
    assert created.session.is_active is False
    assert created.session.revoked_at is not None
    assert not SessionService.verify_token(db_session, created.token)
    assert not SessionService.revoke_session(db_session, created.session.id)


def test_create_session_requires_active_user_and_positive_ttl(db_session):
    user = _create_user(db_session)
    user.is_active = False
    db_session.commit()

    with pytest.raises(ValueError, match="active user not found"):
        SessionService.create_session(db_session, user_id=user.id)
    with pytest.raises(ValueError, match="active user not found"):
        SessionService.create_session(db_session, user_id=999)
    with pytest.raises(ValueError, match="ttl_seconds must be positive"):
        SessionService.create_session(db_session, user_id=user.id, ttl_seconds=0)


def test_hash_token_rejects_empty_token():
    with pytest.raises(ValueError, match="token must not be empty"):
        SessionService.hash_token("")
