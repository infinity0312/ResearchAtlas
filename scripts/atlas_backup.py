"""Consistent SQLite snapshots without importing or initializing the application.

Examples:
  python -m scripts.atlas_backup --output backups/atlas-2026-09-30.db
  python -m scripts.atlas_backup --verify backups/atlas-2026-09-30.db
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import time


ROOT = Path(__file__).resolve().parents[1]


def default_database() -> Path:
    """Match application location while avoiding backend.db import side effects."""
    database_url = os.environ.get("ATLAS_DATABASE_URL")
    if database_url:
        from sqlalchemy.engine import make_url
        url = make_url(database_url)
        if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
            raise ValueError("Backup requires a file-backed SQLite database; supply --database")
        return Path(url.database)
    return Path(os.environ.get("ATLAS_DATA", ROOT / "data")) / "atlas.db"


def _connect_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=20)


def verify_database(database: str | Path) -> dict:
    """Open an existing snapshot read-only and perform SQLite integrity checks."""
    path = Path(database).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("Database must be an existing file")
    with closing(_connect_readonly(path)) as connection:
        results = [row[0] for row in connection.execute("PRAGMA integrity_check")]
        if results != ["ok"]:
            raise ValueError("SQLite integrity check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("SQLite foreign key check failed")
        ledger_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        schema_version = connection.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()[0] if ledger_exists else 0
    return {"database": str(path), "integrity": "ok", "schema_version": schema_version,
            "bytes": path.stat().st_size, "scope": "database_only"}


def backup_database(database: str | Path, output: str | Path, timeout: float = 120) -> dict:
    """Snapshot committed WAL data through SQLite backup, refusing any overwrite."""
    if timeout <= 0:
        raise ValueError("Backup timeout must be positive")
    source = Path(database).expanduser().resolve(strict=True)
    destination = Path(output).expanduser().resolve()
    if not source.is_file():
        raise ValueError("Source database must be an existing file")
    if source == destination:
        raise ValueError("Backup output must differ from source database")
    if any(destination.with_name(destination.name + suffix).exists()
           for suffix in ("-wal", "-shm", "-journal")):
        raise FileExistsError("Backup output already has SQLite sidecar files")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation closes the existence-check race. Delete only our own
    # newly created output if backup/verification fails; never touch the source.
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    started = time.monotonic()

    def progress(status: int, remaining: int, total: int) -> None:
        if time.monotonic() - started > timeout:
            raise TimeoutError("SQLite backup exceeded its timeout")

    try:
        with closing(_connect_readonly(source)) as reader:
            with closing(sqlite3.connect(destination)) as writer:
                reader.backup(writer, pages=256, progress=progress, sleep=0.1)
                # Produce a standalone file even when the source header uses WAL.
                writer.execute("PRAGMA journal_mode=DELETE")
        result = verify_database(destination)
        return {**result, "source": str(source)}
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--output", type=Path, help="New database backup file; existing paths are refused")
    operation.add_argument("--verify", type=Path, help="Verify an existing database snapshot read-only")
    parser.add_argument("--database", type=Path, help="Source SQLite file (default: configured atlas.db)")
    parser.add_argument("--timeout", type=float, default=120, help="Backup timeout in seconds (default: 120)")
    args = parser.parse_args(argv)
    try:
        result = verify_database(args.verify) if args.verify else backup_database(
            args.database if args.database is not None else default_database(), args.output, args.timeout
        )
    except (OSError, ValueError, sqlite3.Error, TimeoutError) as exc:
        parser.exit(1, f"Backup failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
