"""
Tests for DietDB schema constraints and validation
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from dietdb.db import DatabaseManager


@pytest.fixture
def temp_db():
    """Create a temporary database with proper schema and migrations"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Initialize database with migrations
    db_manager = DatabaseManager(db_path)
    db_manager.init_db()

    yield db_path
    db_path.unlink(missing_ok=True)


@pytest.fixture
def temp_db_old():
    """Legacy fixture - kept for reference"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # Create minimal schema
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            verification_status TEXT DEFAULT 'UNVERIFIED'
        );

        CREATE TABLE IF NOT EXISTS nutrients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            category TEXT NOT NULL,
            canonical_unit TEXT NOT NULL,
            is_constrainable INTEGER DEFAULT 0,
            CHECK (is_constrainable IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS food_nutrients (
            food_id INTEGER NOT NULL,
            nutrient_id INTEGER NOT NULL,
            value_canonical REAL,
            canonical_unit TEXT NOT NULL,
            value_status TEXT NOT NULL CHECK(value_status IN (
                'MEASURED', 'TRACE', 'NOT_DETECTED', 'NOT_ANALYSED', 'CALCULATED'
            )),
            source_id INTEGER NOT NULL,
            PRIMARY KEY (food_id, nutrient_id),
            CHECK (value_canonical >= 0 OR value_status IN ('NOT_DETECTED', 'NOT_ANALYSED'))
        );
    """)

    yield db_path
    conn.close()
    db_path.unlink()


class TestSchemaConstraints:
    """Test database schema constraints"""

    def test_nutrient_is_constrainable_boolean(self, temp_db):
        """is_constrainable must be 0 or 1"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Should work
        cursor.execute(
            "INSERT INTO nutrients (canonical_name, display_name, category, canonical_unit, is_constrainable) VALUES (?, ?, ?, ?, ?)",
            ("test1", "Test Nutrient", "MACRO", "g", 1)
        )
        conn.commit()

        # Should fail (constraint violation)
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO nutrients (canonical_name, display_name, category, canonical_unit, is_constrainable) VALUES (?, ?, ?, ?, ?)",
                ("test2", "Test Nutrient 2", "MACRO", "g", 2)
            )
        conn.close()

    def test_value_status_enum(self, temp_db):
        """value_status must be valid enum value"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Insert source first
        cursor.execute("INSERT INTO sources (slug, name) VALUES (?, ?)", ("test", "Test Source"))
        source_id = cursor.lastrowid

        # Insert nutrient
        cursor.execute(
            "INSERT INTO nutrients (canonical_name, display_name, category, canonical_unit) VALUES (?, ?, ?, ?)",
            ("protein", "Protein", "MACRO", "g")
        )
        nutrient_id = cursor.lastrowid

        # Valid statuses should work - use different food_ids
        for idx, status in enumerate(['MEASURED', 'TRACE', 'NOT_DETECTED', 'NOT_ANALYSED', 'CALCULATED'], start=1):
            cursor.execute(
                "INSERT INTO food_nutrients (food_id, nutrient_id, value_canonical, canonical_unit, unit_native, value_status, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (idx, nutrient_id, 10.0, "g", "g", status, source_id)
            )
        conn.commit()

        # Invalid status should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO food_nutrients (food_id, nutrient_id, value_canonical, canonical_unit, unit_native, value_status, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (10, nutrient_id, 10.0, "g", "g", "INVALID_STATUS", source_id)
            )
        conn.close()

    def test_negative_value_requires_not_analysed(self, temp_db):
        """Negative values are only allowed for NOT_DETECTED or NOT_ANALYSED"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Insert source and nutrient
        cursor.execute("INSERT INTO sources (slug, name) VALUES (?, ?)", ("test2", "Test Source 2"))
        source_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO nutrients (canonical_name, display_name, category, canonical_unit) VALUES (?, ?, ?, ?)",
            ("test_nutrient", "Test Nutrient", "MACRO", "g")
        )
        nutrient_id = cursor.lastrowid

        # Negative value with MEASURED should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO food_nutrients (food_id, nutrient_id, value_canonical, canonical_unit, unit_native, value_status, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (1, nutrient_id, -5.0, "g", "g", "MEASURED", source_id)
            )

        # Negative value with NOT_ANALYSED should succeed
        cursor.execute(
            "INSERT INTO food_nutrients (food_id, nutrient_id, value_canonical, canonical_unit, unit_native, value_status, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (2, nutrient_id, -1.0, "g", "g", "NOT_ANALYSED", source_id)
        )
        conn.commit()
        conn.close()


class TestDatabaseSafety:
    """Test connection safety and relationship constraints."""

    def test_foreign_keys_are_enforced(self, temp_db):
        conn = DatabaseManager(temp_db).get_connection()
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO foods (source_code, source_id, english_name) VALUES ('BAD', 999, 'Bad')"
            )
        conn.close()

    def test_food_allergen_pair_is_unique(self, temp_db):
        conn = sqlite3.connect(temp_db)
        conn.execute("PRAGMA foreign_keys = ON")
        source_id = conn.execute(
            "INSERT INTO sources (slug, name) VALUES ('allergen-test', 'Test')"
        ).lastrowid
        food_id = conn.execute(
            "INSERT INTO foods (source_code, source_id, english_name) VALUES ('F001', ?, 'Food')",
            (source_id,),
        ).lastrowid
        allergen_id = conn.execute(
            "INSERT INTO allergens (code, name) VALUES ('milk-test', 'Milk')"
        ).lastrowid
        values = (food_id, allergen_id, 'UNKNOWN', source_id)
        conn.execute(
            "INSERT INTO food_allergens (food_id, allergen_id, presence, source_id) VALUES (?, ?, ?, ?)",
            values,
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO food_allergens (food_id, allergen_id, presence, source_id) VALUES (?, ?, ?, ?)",
                values,
            )
        conn.close()

    def test_read_only_connection_cannot_write(self, temp_db):
        manager = DatabaseManager(temp_db)
        conn = manager.get_connection(readonly=True)
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE should_fail (id INTEGER)")
        conn.close()
