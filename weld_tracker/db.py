"""Database utilities for the WeldLogx application."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = 1


def get_db_path() -> Path:
    """Return the configured database path, ensuring parent directory exists."""
    env_path = os.environ.get("WELDTRACKER_DB", "data/weld_tracker.db")
    path = Path(env_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Create a SQLite connection with safe defaults enabled."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(
        path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        check_same_thread=False,
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def initialize_database(conn: sqlite3.Connection) -> None:
    """Ensure all migrations have been applied."""
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

    applied_versions = {
        row[0] for row in conn.execute("SELECT version FROM schema_migrations")
    }
    if SCHEMA_VERSION in applied_versions:
        return

    for version, script in _migration_scripts():
        if version in applied_versions:
            continue
        _apply_migration(conn, version, script)


def _migration_scripts() -> Iterable[tuple[int, Path]]:
    base = Path(__file__).resolve().parent.parent / "migrations"
    return sorted(
        (
            int(path.name.split("_", 1)[0]),
            path,
        )
        for path in base.glob("[0-9][0-9][0-9]_*.sql")
        if "_down" not in path.name
    )


def _apply_migration(conn: sqlite3.Connection, version: int, script_path: Path) -> None:
    sql = script_path.read_text(encoding="utf-8")
    with conn:
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations(version) VALUES (?)",
            (version,),
        )


__all__ = ["get_connection", "initialize_database", "get_db_path", "SCHEMA_VERSION"]
