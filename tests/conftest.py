"""Test fixtures for DietDB"""

import pytest
import tempfile
from pathlib import Path
import sqlite3

from dietdb.ingest.ifct_loader import IFCTLoader

REPO_ROOT = Path(__file__).parent.parent
CSV_PATH = REPO_ROOT / "data/raw/ifct2017/2.0.0/index.csv"
MAPPING_PATH = REPO_ROOT / "data/mappings/ifct_columns.yaml"
EXPECTED_SHA256 = "22bb9d5072d3907af389cb77deab37a164ba5f84bf2a3eaf1a3fb274f6567ba9"

# Try to import DatabaseManager, but don't fail if not available
try:
    from dietdb.db import DatabaseManager
    HAS_DIETDB = True
except ModuleNotFoundError:
    HAS_DIETDB = False


@pytest.fixture(scope="session")
def ifct_db(tmp_path_factory):
    """Build the IFCT database once for the whole test session."""
    db_file = tmp_path_factory.mktemp("ifct") / "diet.db"
    conn = sqlite3.connect(db_file)
    for migration in sorted((REPO_ROOT / "migrations").glob("*.sql")):
        conn.executescript(migration.read_text())
    conn.close()
    IFCTLoader(str(CSV_PATH), str(MAPPING_PATH), str(db_file), EXPECTED_SHA256).load()
    return db_file


@pytest.fixture(scope="session")
def draft_db(ifct_db, tmp_path_factory):
    """A built working copy with draft rules and conditions loaded."""
    import shutil
    from dietdb.rules import load_conditions, load_rules, seed_reference_data
    db_file = tmp_path_factory.mktemp("draft") / "draft.db"
    shutil.copy2(ifct_db, db_file)
    conn = sqlite3.connect(db_file)
    seed_reference_data(conn, REPO_ROOT / "data/seed")
    conn.commit()
    conn.close()
    load_rules(db_file, REPO_ROOT / "data/rules/draft", "draft-review")
    load_conditions(db_file, REPO_ROOT / "data/conditions/draft_conditions.json")
    return db_file


@pytest.fixture
def db_path():
    """Create a temporary database path with proper schema"""
    if not HAS_DIETDB:
        pytest.skip("DatabaseManager not available")
    
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_file = Path(f.name)
    
    # Initialize database with migrations
    db_manager = DatabaseManager(db_file)
    db_manager.init_db()
    
    yield db_file
    db_file.unlink(missing_ok=True)


@pytest.fixture
def sample_food_nutrient_data():
    """Sample food nutrient data for testing"""
    return {
        "food_code": "A1",
        "food_name": "Rice",
        "group_code": "A",
        "nutrients": {
            "energy_kcal": {"value": 130, "unit": "kcal"},
            "protein": {"value": 2.7, "unit": "g"},
            "fat_total": {"value": 0.3, "unit": "g"},
            "carbohydrate": {"value": 28, "unit": "g"},
        }
    }


@pytest.fixture
def sample_patient_variables():
    """Sample patient profile for rule testing"""
    return {
        "age_years": 45,
        "sex": "M",
        "weight_kg": 70,
        "dx_type2_diabetes": True,
        "dx_ckd": False,
        "egfr_ml_min_1_73m2": 90,
        "hba1c_pct": 7.5,
    }


@pytest.fixture
def sample_rule():
    """Sample diet rule for testing"""
    return {
        "slug": "t2dm_protein_max_test",
        "name": "Type 2 Diabetes - Max Protein (TEST)",
        "kind": "NUTRIENT_BOUND",
        "target_type": "NUTRIENT",
        "target_ref": "protein",
        "min_value": 50,
        "max_value": 100,
        "unit": "g",
        "basis": "PER_DAY",
        "tier": "THERAPEUTIC",
        "enforcement": "HARD",
        "applies_when": {"var": "dx_type2_diabetes", "op": "==", "value": True},
        "rationale": "Moderate protein for blood sugar control",
        "status": "TEST_FIXTURE"
    }
