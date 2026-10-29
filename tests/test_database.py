

class TestSqliteWalHardening:
    """Verify the application engine enables WAL/busy_timeout on file-backed
    SQLite and leaves in-memory SQLite (and non-SQLite engines) untouched.
    """

    def _reload_with_url(self, monkeypatch, url, tmp_path_obj=None):
        import importlib

        from app import config as app_config
        from app import database as app_database

        original_settings = app_config.get_settings()
        monkeypatch.setattr(app_config, "get_settings", lambda: original_settings)
        settings = app_config.get_settings()
        monkeypatch.setattr(settings, "database_url", url)
        importlib.reload(app_database)
        return app_database, settings

    def test_file_backed_sqlite_uses_wal_and_busy_timeout(self, monkeypatch, tmp_path):
        import importlib
        import os

        from app import config as app_config
        from app import database as app_database

        db_path = tmp_path / "wal.db"
        url = f"sqlite:///{db_path}"

        original_get_settings = app_config.get_settings
        original_settings = original_get_settings()
        monkeypatch.setattr(app_config, "get_settings", lambda: original_settings)
        monkeypatch.setattr(original_settings, "database_url", url)

        importlib.reload(app_database)
        try:
            engine = app_database.engine
            with engine.connect() as conn:
                journal_mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
                busy_timeout = conn.exec_driver_sql("PRAGMA busy_timeout").scalar()
            assert str(journal_mode).lower() == "wal"
            assert int(busy_timeout) == 5000
            # Ensure no runtime artifact in the repo root.
            assert not os.path.exists("releaseguard.db")
        finally:
            app_database.engine.dispose()
            monkeypatch.setattr(
                app_config,
                "get_settings",
                lambda: original_settings.__class__(),
            )
            importlib.reload(app_database)

    def test_in_memory_sqlite_is_not_forced_to_wal(self, monkeypatch):
        import importlib

        from app import config as app_config
        from app import database as app_database

        original_get_settings = app_config.get_settings
        original_settings = original_get_settings()
        monkeypatch.setattr(app_config, "get_settings", lambda: original_settings)
        monkeypatch.setattr(original_settings, "database_url", "sqlite:///:memory:")

        importlib.reload(app_database)
        try:
            engine = app_database.engine
            with engine.connect() as conn:
                journal_mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
            assert str(journal_mode).lower() == "memory"
        finally:
            app_database.engine.dispose()
            importlib.reload(app_database)
