"""G3 rule-loader contract tests."""

import sqlite3
from pathlib import Path

import pytest

from dietdb.db import DatabaseManager
from dietdb.rules import load_rules


ROOT = Path(__file__).parent.parent


@pytest.fixture
def rules_db(tmp_path):
    path = tmp_path / "rules.db"
    DatabaseManager(path).init_db()
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO nutrients (canonical_name, display_name, category, canonical_unit) VALUES ('protein', 'Protein', 'MACRONUTRIENT', 'g')")
    conn.commit()
    conn.close()
    return path


def test_test_mode_accepts_fixture_and_seeds_reference_data(rules_db):
    assert load_rules(rules_db, ROOT / "data/rules", "test") == 1
    conn = sqlite3.connect(rules_db)
    assert conn.execute("SELECT COUNT(*) FROM allergens").fetchone()[0] == 14
    assert conn.execute("SELECT status FROM rules").fetchone()[0] == "TEST_FIXTURE"
    conn.close()


def test_production_rejects_fixture(rules_db):
    with pytest.raises(ValueError, match="not loadable"):
        load_rules(rules_db, ROOT / "data/rules", "production")


def test_unknown_variable_and_malformed_expression_rejected(rules_db, tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("[{\"slug\":\"bad\",\"name\":\"bad\",\"kind\":\"NUTRIENT_BOUND\",\"target_type\":\"NUTRIENT\",\"target_ref\":\"protein\",\"basis\":\"PER_DAY\",\"tier\":\"THERAPEUTIC\",\"enforcement\":\"HARD\",\"applies_when\":{\"var\":\"missing\",\"op\":\"==\",\"value\":true},\"rationale\":\"FAKE FIXTURE, NOT MEDICAL\",\"status\":\"TEST_FIXTURE\"}]")
    with pytest.raises(ValueError, match="unknown patient variable"):
        load_rules(rules_db, tmp_path, "test")
