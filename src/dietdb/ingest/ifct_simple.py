"""IFCT 2017 Loader"""
import csv
import hashlib
import sqlite3
import urllib.request
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

IFCT_DATA_URL = "https://raw.githubusercontent.com/nodef/ifct2017/main/compositions/index.csv"
IFCT_VERSION = "2.0.0"


class IfctLoader:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.source_id = None
        self.nutrient_map = {}
        self.data_dir = db_path.parent / "data" / "raw" / "ifct2017" / IFCT_VERSION
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        csv_path = self._download_data()
        self._register_source(cursor)
        self._load_nutrients_from_csv(cursor, csv_path)
        self._load_food_groups(cursor)
        self._load_foods_from_csv(cursor, csv_path)
        conn.commit()
        conn.close()
        logger.info("IFCT 2017 data loaded")

    def _download_data(self) -> Path:
        csv_path = self.data_dir / "index.csv"
        if csv_path.exists():
            return csv_path
        logger.info("Downloading IFCT 2017 data...")
        req = urllib.request.Request(IFCT_DATA_URL, headers={"User-Agent": "DietDB/1.0"})
        with urllib.request.urlopen(req) as response:
            data = response.read()
        csv_path.write_bytes(data)
        (self.data_dir / "manifest.sha256").write_text(hashlib.sha256(data).hexdigest())
        return csv_path

    def _register_source(self, cursor: sqlite3.Cursor) -> None:
        cursor.execute(
            """INSERT OR IGNORE INTO sources 
            (slug, name, version, year, publisher, verification_status)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ("ifct2017", "Indian Food Composition Tables 2017", IFCT_VERSION, 2017,
             "National Institute of Nutrition", "UNVERIFIED")
        )
        cursor.execute("SELECT id FROM sources WHERE slug = 'ifct2017'")
        self.source_id = cursor.fetchone()[0]

    def _load_nutrients_from_csv(self, cursor: sqlite3.Cursor, csv_path: Path) -> None:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)

        nutrient_mapping = {
            "enerc": ("energy_kcal", "Energy", "kcal", "ENERGY"),
            "protcnt": ("protein", "Protein", "g", "MACRO"),
            "fatce": ("fat_total", "Total Fat", "g", "MACRO"),
            "choavldf": ("carbohydrate", "Available Carbohydrate", "g", "MACRO"),
            "fibtg": ("dietary_fibre", "Dietary Fibre", "g", "MACRO"),
            "ca": ("calcium", "Calcium", "mg", "MINERAL"),
            "fe": ("iron", "Iron", "mg", "MINERAL"),
            "p": ("phosphorus", "Phosphorus", "mg", "MINERAL"),
            "k": ("potassium", "Potassium", "mg", "MINERAL"),
            "na": ("sodium", "Sodium", "mg", "MINERAL"),
        }

        for col_name in headers:
            if col_name.endswith("_e") or col_name not in nutrient_mapping:
                continue
            canonical, display, unit, category = nutrient_mapping[col_name]
            cursor.execute(
                """INSERT OR IGNORE INTO nutrients
                (canonical_name, display_name, canonical_unit, category, is_constrainable)
                VALUES (?, ?, ?, ?, ?)""",
                (canonical, display, unit, category, 1)
            )
            cursor.execute("SELECT id FROM nutrients WHERE canonical_name = ?", (canonical,))
            result = cursor.fetchone()
            if result:
                self.nutrient_map[col_name] = result[0]
            else:
                logger.warning(f"Failed to load nutrient: {canonical}")

    def _load_food_groups(self, cursor: sqlite3.Cursor) -> None:
        groups = [("A", "Cereals and Millets"), ("B", "Vegetables"), 
                  ("C", "Fruits"), ("H", "Legumes")]
        for code, name in groups:
            cursor.execute("INSERT OR IGNORE INTO food_groups (code, name) VALUES (?, ?)", (code, name))

    def _parse_value(self, raw: str):
        raw = str(raw).strip() if raw else ""
        if not raw or raw.upper() in ["NA", "-"]:
            return None, "NOT_ANALYSED"
        if raw.upper() == "TR":
            return 0.001, "TRACE"
        try:
            return float(raw.replace(",", "")), "MEASURED"
        except:
            return None, "NOT_ANALYSED"

    def _load_foods_from_csv(self, cursor: sqlite3.Cursor, csv_path: Path) -> None:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            food_count = 0
            for row in reader:
                code = row.get("code", "").strip()
                name = row.get("name", "").strip()
                if not code or not name:
                    continue
                cursor.execute(
                    """INSERT OR REPLACE INTO foods
                    (source_code, source_id, english_name, food_state)
                    VALUES (?, ?, ?, ?)""",
                    (code, self.source_id, name, "RAW")
                )
                cursor.execute("SELECT id FROM foods WHERE source_code = ? AND source_id = ?", (code, self.source_id))
                food_id = cursor.fetchone()[0]
                food_count += 1
                for col_name, nutrient_id in self.nutrient_map.items():
                    raw_value = row.get(col_name, "")
                    value, status = self._parse_value(raw_value)
                    if value is None:
                        continue
                    cursor.execute("SELECT canonical_unit FROM nutrients WHERE id = ?", (nutrient_id,))
                    unit = cursor.fetchone()[0]
                    cursor.execute(
                        """INSERT OR REPLACE INTO food_nutrients
                        (food_id, nutrient_id, value_canonical, canonical_unit, 
                         unit_native, value_status, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (food_id, nutrient_id, value, unit, unit, status, self.source_id)
                    )
        logger.info(f"Loaded {food_count} foods")
