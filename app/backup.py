"""Local SQLite backup helpers for ReleaseGuard.

This module exposes two stdlib-only helpers and a small CLI:

* :func:`create_backup` copies a file-backed SQLite database into a
  backup directory using a ``releaseguard-backup-*.db`` filename.
* :func:`restore_backup` replaces a target SQLite database file with a
  previously created backup, including any ``-wal`` / ``-shm`` sidecars.
* ``python -m app.backup`` provides ``create`` and ``restore``
  subcommands that exit with a non-zero status on invalid inputs.

The helpers intentionally avoid importing :mod:`app.database` so the
backup command can run independently of the FastAPI runtime path.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
import sys
from typing import Optional


_BACKUP_PREFIX = "releaseguard-backup-"
_BACKUP_SUFFIX = ".db"


def _ensure_str(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _backup_filename(now: Optional[_dt.datetime] = None) -> str:
    timestamp_source = now or _dt.datetime.now()
    timestamp = timestamp_source.strftime("%Y%m%d-%H%M%S")
    return f"{_BACKUP_PREFIX}{timestamp}{_BACKUP_SUFFIX}"


def create_backup(database_path: str, backup_dir: str) -> str:
    """Copy ``database_path`` into ``backup_dir`` and return the backup path.

    The backup directory is created if it does not already exist. The
    backup filename starts with ``releaseguard-backup-`` and ends with
    ``.db``. Raises :class:`FileNotFoundError` if ``database_path`` does
    not exist.
    """
    src = _ensure_str("database_path", database_path)
    dst_dir = _ensure_str("backup_dir", backup_dir)
    if not os.path.exists(src):
        raise FileNotFoundError(f"source database not found: {src}")
    os.makedirs(dst_dir, exist_ok=True)
    backup_name = _backup_filename()
    backup_path = os.path.join(dst_dir, backup_name)
    shutil.copy2(src, backup_path)
    return backup_path


def _sidecar_paths(database_path: str):
    return [f"{database_path}-wal", f"{database_path}-shm"]


def restore_backup(backup_path: str, database_path: str) -> str:
    """Replace ``database_path`` with ``backup_path`` and return the target path.

    Creates the parent directory of ``database_path`` if needed. Any
    ``-wal`` / ``-shm`` sidecars next to the target are removed so the
    restored database is not shadowed by stale write-ahead-log state.
    Raises :class:`FileNotFoundError` if ``backup_path`` does not exist.
    """
    src = _ensure_str("backup_path", backup_path)
    dst = _ensure_str("database_path", database_path)
    if not os.path.exists(src):
        raise FileNotFoundError(f"backup file not found: {src}")
    parent = os.path.dirname(os.path.abspath(dst))
    if parent:
        os.makedirs(parent, exist_ok=True)
    for sidecar in _sidecar_paths(dst):
        if os.path.exists(sidecar):
            os.remove(sidecar)
    if os.path.exists(dst):
        os.remove(dst)
    shutil.copy2(src, dst)
    return dst


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.backup",
        description="ReleaseGuard local SQLite backup utilities.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="create a backup of a SQLite database")
    create.add_argument("--database", required=True, help="path to the source SQLite database file")
    create.add_argument("--backup-dir", required=True, help="directory to write the backup file into")

    restore = subparsers.add_parser("restore", help="restore a SQLite database from a backup file")
    restore.add_argument("--backup", required=True, help="path to the backup file to restore from")
    restore.add_argument("--database", required=True, help="path to the target SQLite database file")

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "create":
        try:
            backup_path = create_backup(args.database, args.backup_dir)
        except FileNotFoundError as exc:
            print(f"create_backup failed: {exc}", file=sys.stderr)
            return 2
        except ValueError as exc:
            print(f"create_backup failed: {exc}", file=sys.stderr)
            return 2
        print(backup_path)
        return 0

    if args.command == "restore":
        try:
            database_path = restore_backup(args.backup, args.database)
        except FileNotFoundError as exc:
            print(f"restore_backup failed: {exc}", file=sys.stderr)
            return 2
        except ValueError as exc:
            print(f"restore_backup failed: {exc}", file=sys.stderr)
            return 2
        print(database_path)
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
