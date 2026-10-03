"""
DietDB - Database initialization and migration management
"""

import sqlite3
import hashlib
import json
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database and migrations"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self, readonly: bool = False) -> sqlite3.Connection:
        """Get database connection"""
        if readonly and not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        if readonly:
            conn = sqlite3.connect(
                f"file:{self.db_path.resolve()}?mode=ro", uri=True, check_same_thread=False
            )
        else:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        """Initialize database from migrations"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create schema_version table if not exists
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now')),
                script_name TEXT NOT NULL,
                checksum TEXT NOT NULL
            )
            """
        )

        # Get current version
        cursor.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()
        current_version = result[0] if result[0] else 0

        # Apply migrations
        migrations_dir = Path(__file__).parent.parent.parent / "migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))

        for migration_file in migration_files:
            # Extract version from filename (e.g., "001_initial_schema.sql")
            version = int(migration_file.name.split("_")[0])

            if version > current_version:
                logger.info(f"Applying migration {version}: {migration_file.name}")
                with open(migration_file) as f:
                    sql_content = f.read()

                # Calculate checksum
                checksum = hashlib.sha256(sql_content.encode()).hexdigest()

                # Execute migration
                cursor.executescript(sql_content)

                # Record migration
                cursor.execute(
                    """
                    INSERT INTO schema_version (version, script_name, checksum)
                    VALUES (?, ?, ?)
                    """,
                    (version, migration_file.name, checksum),
                )

                logger.info(f"Migration {version} applied successfully")

        conn.commit()
        conn.close()

    def get_db_hash(self) -> str:
        """Get deterministic hash of logical database contents"""
        conn = self.get_connection(readonly=True)
        cursor = conn.cursor()

        # Get all table schemas and sorted data
        hasher = hashlib.sha256()

        # Get list of tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            # Skip internal tables
            if table.startswith("sqlite_"):
                continue

            hasher.update(table.encode())

            # Get all rows sorted by primary key
            cursor.execute(f"SELECT * FROM {table} ORDER BY rowid")
            rows = cursor.fetchall()

            for row in rows:
                row_str = json.dumps(list(row), sort_keys=True, default=str)
                hasher.update(row_str.encode())

        conn.close()
        return hasher.hexdigest()
