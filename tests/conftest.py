"""Test fixtures for DietDB"""

import pytest
import tempfile
from pathlib import Path

# Try to import DatabaseManager, but don't fail if not available
try:
    from dietdb.db import DatabaseManager
    HAS_DIETDB = True
except ModuleNotFoundError:
    HAS_DIETDB = False


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
        "has_t2dm": True,
        "has_ckd": False,
        "egfr": 90,
        "hba1c_percent": 7.5,
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
        "applies_when": {"op": "eq", "field": "has_t2dm", "value": True},
        "rationale": "Moderate protein for blood sugar control",
        "status": "TEST_FIXTURE"
    }
