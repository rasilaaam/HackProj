"""IFCT 2017 Data Loader"""
import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class IfctLoader:
    """Loads IFCT 2017 data into database"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.source_id = None

    def load(self) -> None:
        """Main loader orchestration"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        self._register_source(cursor)
        self._load_nutrients(cursor)
        self._load_food_groups(cursor)
        self._load_test_foods(cursor)
        self._load_patient_variables(cursor)
        self._load_allergens(cursor)

        conn.commit()
        conn.close()
        logger.info("IFCT 2017 data loading complete")

    def _register_source(self, cursor: sqlite3.Cursor) -> None:
        """Register IFCT 2017 as data source"""
        cursor.execute(
            """INSERT OR IGNORE INTO sources 
            (slug, name, description, version, year, publisher, license, verification_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("ifct2017", "Indian Food Composition Tables 2017",
             "Food composition data from NIN/ICMR", "1.0", 2017,
             "National Institute of Nutrition, Hyderabad",
             "TBD - Awaiting clarification", "UNVERIFIED_AGAINST_OFFICIAL_SOURCE")
        )
        cursor.execute("SELECT id FROM sources WHERE slug = 'ifct2017'")
        self.source_id = cursor.fetchone()[0]

    def _load_nutrients(self, cursor: sqlite3.Cursor) -> None:
        """Load nutrient definitions"""
        nutrients = [
            ("energy_kcal", "Energy (kcal)", "ENERGY", "kcal", "3", 1),
            ("protein", "Protein", "MACRO", "g", "4", 1),
            ("fat_total", "Total Fat", "MACRO", "g", "5", 1),
            ("carbohydrate", "Carbohydrate", "MACRO", "g", "6", 1),
            ("calcium", "Calcium", "MINERAL", "mg", "9", 1),
            ("iron", "Iron", "MINERAL", "mg", "11", 1),
            ("sodium", "Sodium", "MINERAL", "mg", "13", 1),
            ("potassium", "Potassium", "MINERAL", "mg", "14", 1),
            ("vitamin_c", "Vitamin C", "VITAMIN", "mg", "17", 1),
        ]

        for idx, (name, display, category, unit, ifct_code, constrainable) in enumerate(nutrients):
            cursor.execute(
                """INSERT OR IGNORE INTO nutrients
                (canonical_name, display_name, category, canonical_unit, ifct_column_code,
                 is_constrainable, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name, display, category, unit, ifct_code, constrainable, idx)
            )

    def _load_food_groups(self, cursor: sqlite3.Cursor) -> None:
        """Load IFCT food group hierarchy"""
        groups = [
            ("A", "Cereals, Grains and Their Products"),
            ("B", "Vegetables"),
            ("C", "Fruits"),
            ("H", "Legumes and Legume Products"),
        ]
        for code, name in groups:
            cursor.execute("INSERT OR IGNORE INTO food_groups (code, name) VALUES (?, ?)", (code, name))

    def _load_test_foods(self, cursor: sqlite3.Cursor) -> None:
        """Load test food items"""
        test_foods = [
            ("A1", "Rice", "Oryza sativa", "A"),
            ("B1", "Carrot", "Daucus carota", "B"),
            ("C1", "Banana", "Musa paradisiaca", "C"),
            ("H1", "Chick Pea", "Cicer arietinum", "H"),
        ]

        for code, english_name, scientific_name, group_code in test_foods:
            cursor.execute("SELECT id FROM food_groups WHERE code = ?", (group_code,))
            group_id = cursor.fetchone()[0]
            cursor.execute(
                """INSERT OR IGNORE INTO foods
                (source_code, source_id, english_name, scientific_name, food_group_id, food_state)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (code, self.source_id, english_name, scientific_name, group_id, "RAW")
            )

    def _load_patient_variables(self, cursor: sqlite3.Cursor) -> None:
        """Load patient variables"""
        variables = [
            ("age_years", "Age (years)", "INTEGER", "years", 0, 120, "LAB_REPORT"),
            ("sex", "Sex", "ENUM", None, None, None, "USER_ENTERED"),
            ("has_t2dm", "Has Type 2 Diabetes", "BOOLEAN", None, None, None, "LAB_REPORT"),
            ("egfr", "eGFR", "REAL", "mL/min/1.73m²", 0, 120, "LAB_REPORT"),
        ]

        for var_name, display_name, dtype, unit, min_val, max_val, source in variables:
            cursor.execute(
                """INSERT OR IGNORE INTO patient_variables
                (variable_name, display_name, data_type, unit, min_value, max_value, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (var_name, display_name, dtype, unit, min_val, max_val, source)
            )

    def _load_allergens(self, cursor: sqlite3.Cursor) -> None:
        """Load allergen definitions"""
        allergens = [("milk", "Milk"), ("egg", "Egg"), ("peanut", "Peanut")]
        for code, name in allergens:
            cursor.execute("INSERT OR IGNORE INTO allergens (code, name) VALUES (?, ?)", (code, name))
