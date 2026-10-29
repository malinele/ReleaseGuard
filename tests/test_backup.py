
import os

import pytest


class TestReleaseGuardBackup:
    """Coverage for app.backup create_backup / restore_backup helpers and CLI."""

    def _make_sqlite(self, path):
        import sqlite3

        connection = sqlite3.connect(str(path))
        try:
            connection.execute("CREATE TABLE example (id INTEGER PRIMARY KEY, value TEXT)")
            connection.execute("INSERT INTO example (value) VALUES ('seed')")
            connection.commit()
        finally:
            connection.close()

    def test_create_backup_writes_releaseguard_backup_file(self, tmp_path):
        from app.backup import create_backup

        database_path = tmp_path / "source.db"
        backup_dir = tmp_path / "backups"
        self._make_sqlite(database_path)

        backup_path = create_backup(str(database_path), str(backup_dir))

        assert os.path.isdir(backup_dir)
        assert os.path.exists(backup_path)
        assert os.path.basename(backup_path).startswith("releaseguard-backup-")
        assert os.path.basename(backup_path).endswith(".db")

    def test_create_backup_round_trip_with_restore(self, tmp_path):
        from app.backup import create_backup, restore_backup

        database_path = tmp_path / "source.db"
        backup_dir = tmp_path / "backups"
        self._make_sqlite(database_path)

        backup_path = create_backup(str(database_path), str(backup_dir))
        assert os.path.exists(backup_path)

        os.remove(database_path)
        restore_backup(backup_path, str(database_path))

        import sqlite3

        connection = sqlite3.connect(str(database_path))
        try:
            rows = connection.execute("SELECT value FROM example").fetchall()
        finally:
            connection.close()
        assert rows == [("seed",)]

    def test_create_backup_raises_for_missing_source(self, tmp_path):
        from app.backup import create_backup

        missing = tmp_path / "does_not_exist.db"
        backup_dir = tmp_path / "backups"

        with pytest.raises(FileNotFoundError):
            create_backup(str(missing), str(backup_dir))

    def test_create_backup_creates_backup_directory(self, tmp_path):
        from app.backup import create_backup

        database_path = tmp_path / "source.db"
        backup_dir = tmp_path / "nested" / "backups"
        self._make_sqlite(database_path)

        create_backup(str(database_path), str(backup_dir))

        assert backup_dir.is_dir()
        entries = [p for p in backup_dir.iterdir() if p.is_file()]
        assert entries, "backup directory should contain the new backup file"

    def test_restore_backup_raises_for_missing_backup(self, tmp_path):
        from app.backup import restore_backup

        missing = tmp_path / "missing.db"
        database_path = tmp_path / "target.db"

        with pytest.raises(FileNotFoundError):
            restore_backup(str(missing), str(database_path))

    def test_restore_backup_creates_parent_directory(self, tmp_path):
        from app.backup import restore_backup

        backup_path = tmp_path / "seed.db"
        self._make_sqlite(backup_path)
        database_path = tmp_path / "nested" / "store" / "target.db"

        restore_backup(str(backup_path), str(database_path))

        assert database_path.exists()

    def test_cli_create_and_restore_round_trip(self, tmp_path, capsys):
        from app.backup import main

        database_path = tmp_path / "cli_source.db"
        backup_dir = tmp_path / "cli_backups"
        target_path = tmp_path / "cli_target.db"
        self._make_sqlite(database_path)

        create_exit = main(["create", "--database", str(database_path), "--backup-dir", str(backup_dir)])
        captured = capsys.readouterr()
        backup_path = captured.out.strip()
        assert create_exit == 0
        assert backup_path and os.path.exists(backup_path)
        assert os.path.basename(backup_path).startswith("releaseguard-backup-")
        assert os.path.basename(backup_path).endswith(".db")

        restore_exit = main(["restore", "--backup", backup_path, "--database", str(target_path)])
        captured = capsys.readouterr()
        assert restore_exit == 0
        assert captured.out.strip() == str(target_path)
        assert target_path.exists()

    def test_cli_create_exits_nonzero_for_missing_source(self, tmp_path):
        from app.backup import main

        missing = tmp_path / "missing_src.db"
        backup_dir = tmp_path / "cli_backups_missing"

        exit_code = main(["create", "--database", str(missing), "--backup-dir", str(backup_dir)])

        assert exit_code != 0

    def test_cli_restore_exits_nonzero_for_missing_backup(self, tmp_path):
        from app.backup import main

        missing = tmp_path / "missing_backup.db"
        database_path = tmp_path / "cli_target_missing.db"

        exit_code = main(["restore", "--backup", str(missing), "--database", str(database_path)])

        assert exit_code != 0
