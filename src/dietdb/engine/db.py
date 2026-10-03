"""Read-only SQLite connection helpers used by the planning engine."""
import sqlite3
from pathlib import Path


def connect_readonly(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
