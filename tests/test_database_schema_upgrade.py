"""SQLite schema upgrade tests for local runtime databases."""

from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.database import ensure_sqlite_schema_upgrades


def _create_legacy_users_table(db_path: Path):
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    username VARCHAR(100) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    display_name VARCHAR(200),
                    role VARCHAR(32) NOT NULL DEFAULT 'viewer',
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO users (
                    id,
                    username,
                    password_hash,
                    role,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (
                    1,
                    'existing-user',
                    'hash',
                    'viewer',
                    1,
                    '2026-01-01 00:00:00',
                    '2026-01-01 00:00:00'
                )
                """
            )
        )
    return engine


def test_sqlite_schema_upgrade_adds_user_lockout_columns(tmp_path):
    """Existing SQLite users tables gain lockout columns without losing rows."""
    db_path = tmp_path / "releaseguard.db"
    engine = _create_legacy_users_table(db_path)

    ensure_sqlite_schema_upgrades(engine)

    columns = {column["name"]: column for column in inspect(engine).get_columns("users")}
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT username, failed_login_attempts, locked_until FROM users WHERE id = 1")
        ).one()

    assert "failed_login_attempts" in columns
    assert "locked_until" in columns
    assert columns["failed_login_attempts"]["nullable"] is False
    assert row.username == "existing-user"
    assert row.failed_login_attempts == 0
    assert row.locked_until is None


def test_sqlite_schema_upgrade_is_idempotent(tmp_path):
    """Running the upgrade more than once must be safe."""
    db_path = tmp_path / "releaseguard.db"
    engine = _create_legacy_users_table(db_path)

    ensure_sqlite_schema_upgrades(engine)
    ensure_sqlite_schema_upgrades(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    assert {"failed_login_attempts", "locked_until"}.issubset(columns)


def test_sqlite_schema_upgrade_ignores_databases_without_users_table(tmp_path):
    """Fresh databases without users table are left for Base.create_all."""
    db_path = tmp_path / "releaseguard.db"
    engine = create_engine(f"sqlite:///{db_path}")

    ensure_sqlite_schema_upgrades(engine)

    assert "users" not in inspect(engine).get_table_names()
