"""Bootstrap the first local owner user.

Usage:
    RELEASEGUARD_OWNER_PASSWORD='...' python scripts/create_owner.py [--username NAME]

The password is read only from the RELEASEGUARD_OWNER_PASSWORD environment
variable so it never appears in argv or shell history. The script refuses to
run when an owner already exists.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session  # noqa: E402

from app.models.user import User  # noqa: E402
from app.services.user_service import UserService  # noqa: E402

PASSWORD_ENV_VAR = "RELEASEGUARD_OWNER_PASSWORD"
DEFAULT_OWNER_USERNAME = "owner"
OWNER_ROLE = "owner"


def create_owner(db: Session, *, username: str, password: str) -> User:
    """Create the bootstrap owner; raise ValueError if one already exists."""
    if not password:
        raise ValueError(f"{PASSWORD_ENV_VAR} must be set to a non-empty value")
    if db.query(User).filter(User.role == OWNER_ROLE).first():
        raise ValueError("an owner user already exists")
    return UserService.create_user(
        db,
        username=username,
        password=password,
        display_name="Owner",
        role=OWNER_ROLE,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create the bootstrap owner user.")
    parser.add_argument("--username", default=DEFAULT_OWNER_USERNAME)
    args = parser.parse_args(argv)

    password = os.environ.get(PASSWORD_ENV_VAR, "")
    if not password:
        print(f"error: {PASSWORD_ENV_VAR} is not set", file=sys.stderr)
        return 2

    from app.database import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        user = create_owner(db, username=args.username, password=password)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(f"created owner user '{user.username}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
