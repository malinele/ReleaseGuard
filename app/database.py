"""Database configuration and session management."""
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import get_settings


def _is_file_backed_sqlite(url):
    """Return True only for file-backed sqlite URLs (sqlite:///... and not :memory:)."""
    if not isinstance(url, str):
        return False
    if not url.startswith("sqlite:///"):
        return False
    if ":memory:" in url or "mode=memory" in url:
        return False
    return True

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


if _is_file_backed_sqlite(get_settings().database_url):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_sqlite_schema_upgrades(target_engine):
    """Apply small idempotent SQLite upgrades for existing local databases."""
    if target_engine.dialect.name != "sqlite":
        return

    inspector = inspect(target_engine)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    statements = []
    if "failed_login_attempts" not in existing_columns:
        statements.append(
            "ALTER TABLE users "
            "ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0"
        )
    if "locked_until" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN locked_until DATETIME")

    if not statements:
        return

    with target_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema_upgrades(engine)
