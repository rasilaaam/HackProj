"""
DietDB - Read-only repository API
"""

import sqlite3
from pathlib import Path
from typing import Optional, Sequence
import logging

logger = logging.getLogger(__name__)


class DietDB:
    """Read-only access to diet planning database"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get read-only database connection"""
        uri = f"file:{self.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def search_foods(self, query: str, limit: int = 10) -> list[dict]:
        """Search foods by name or alias"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT DISTINCT f.id, f.english_name, f.scientific_name
            FROM food_aliases_fts fts
            JOIN food_aliases fa ON fts.rowid = fa.id
            JOIN foods f ON fa.food_id = f.id
            WHERE food_aliases_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_nutrients(self, food_id: int, nutrient_ids: Optional[Sequence[str]] = None) -> dict:
        """Get nutrients for a food"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if nutrient_ids:
            placeholders = ",".join("?" * len(nutrient_ids))
            query = f"""
                SELECT n.canonical_name, fn.value_canonical, fn.canonical_unit,
                       fn.value_status, fn.source_id, fn.raw_text, fn.sd
                FROM food_nutrients fn
                JOIN nutrients n ON fn.nutrient_id = n.id
                WHERE fn.food_id = ? AND n.canonical_name IN ({placeholders})
                ORDER BY n.sort_order
            """
            cursor.execute(query, [food_id] + list(nutrient_ids))
        else:
            cursor.execute(
                """
                SELECT n.canonical_name, fn.value_canonical, fn.canonical_unit,
                       fn.value_status, fn.source_id, fn.raw_text, fn.sd
                FROM food_nutrients fn
                JOIN nutrients n ON fn.nutrient_id = n.id
                WHERE fn.food_id = ?
                ORDER BY n.sort_order
                """,
                (food_id,),
            )

        result = {
            row["canonical_name"]: {
                "value": row["value_canonical"],
                "unit": row["canonical_unit"],
                "status": row["value_status"],
                "source_id": row["source_id"],
                "raw_text": row["raw_text"],
                "sd": row["sd"],
            }
            for row in cursor.fetchall()
        }

        conn.close()
        return result
