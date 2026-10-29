"""Tests for the bootstrap owner script."""
import importlib.util
from pathlib import Path

import pytest

from app.models.user import User
from app.services.user_service import UserService

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "create_owner.py"
_spec = importlib.util.spec_from_file_location("create_owner", SCRIPT_PATH)
create_owner_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(create_owner_module)


def test_create_owner_stores_hashed_password_with_owner_role(db_session):
    user = create_owner_module.create_owner(
        db_session, username="boss", password="s3cret-pass"
    )

    assert user.role == "owner"
    assert user.is_active is True
    assert user.password_hash != "s3cret-pass"
    assert UserService.verify_user_password(db_session, "boss", "s3cret-pass")


def test_create_owner_rejects_empty_password(db_session):
    with pytest.raises(ValueError):
        create_owner_module.create_owner(db_session, username="boss", password="")

    assert db_session.query(User).count() == 0


def test_create_owner_refuses_when_owner_exists(db_session):
    create_owner_module.create_owner(db_session, username="boss", password="pw-one")

    with pytest.raises(ValueError, match="already exists"):
        create_owner_module.create_owner(db_session, username="other", password="pw-two")

    assert db_session.query(User).count() == 1


def test_main_fails_without_password_env(monkeypatch, capsys):
    monkeypatch.delenv("RELEASEGUARD_OWNER_PASSWORD", raising=False)

    assert create_owner_module.main([]) == 2
    assert "RELEASEGUARD_OWNER_PASSWORD" in capsys.readouterr().err
