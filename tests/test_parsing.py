"""Assertions for IFCT status, unit, metadata, and state parsing."""

import sqlite3

from dietdb.aliases import extract_regional_names


def _one(db_path, query, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(query, params).fetchone()
    finally:
        conn.close()


def test_zero_on_analysed_food_is_not_detected(ifct_db):
    row = _one(
        ifct_db,
        """SELECT value_canonical, value_status FROM food_nutrients fn
           JOIN foods f ON f.id = fn.food_id
           WHERE f.source_code != 'T001' AND fn.value_native = 0 LIMIT 1""",
    )
    assert row == (None, "NOT_DETECTED")


def test_measured_values_are_never_zero(ifct_db):
    assert _one(
        ifct_db,
        "SELECT COUNT(*) FROM food_nutrients WHERE value_status = 'MEASURED' AND value_canonical = 0",
    )[0] == 0


def test_group_t_non_fatty_acids_are_not_analysed(ifct_db):
    count = _one(
        ifct_db,
        """SELECT COUNT(*) FROM food_nutrients fn
           JOIN foods f ON f.id = fn.food_id
           JOIN nutrients n ON n.id = fn.nutrient_id
           JOIN food_groups g ON g.id = f.food_group_id
           WHERE g.code = 'T' AND n.ifct_column_code IN ('enerc', 'protcnt', 'ca', 'p', 'k', 'na', 'fe')
             AND fn.value_status != 'NOT_ANALYSED'""",
    )[0]
    assert count == 0


def test_rice_unit_conversions(ifct_db):
    assert _one(
        ifct_db,
        """SELECT n.ifct_column_code, fn.value_canonical, fn.canonical_unit
           FROM food_nutrients fn JOIN nutrients n ON n.id = fn.nutrient_id
           JOIN foods f ON f.id = fn.food_id WHERE f.source_code = 'A015'
             AND n.ifct_column_code = 'k'""",
    ) == ("k", 108.0, "mg")
    assert _one(
        ifct_db,
        """SELECT fn.value_canonical, fn.canonical_unit FROM food_nutrients fn
           JOIN nutrients n ON n.id = fn.nutrient_id JOIN foods f ON f.id = fn.food_id
           WHERE f.source_code = 'A015' AND n.ifct_column_code = 'fe'""",
    ) == (0.65, "mg")
    assert _one(
        ifct_db,
        """SELECT fn.value_canonical, fn.canonical_unit FROM food_nutrients fn
           JOIN nutrients n ON n.id = fn.nutrient_id JOIN foods f ON f.id = fn.food_id
           WHERE f.source_code = 'A015' AND n.ifct_column_code = 'vitk1'""",
    ) == (1.5, "ug")


def test_energy_and_sd_use_the_same_factor(ifct_db):
    energy = _one(
        ifct_db,
        """SELECT fn.value_native, fn.value_canonical, fn.sd FROM food_nutrients fn
           JOIN nutrients n ON n.id = fn.nutrient_id JOIN foods f ON f.id = fn.food_id
           WHERE f.source_code = 'A015' AND n.ifct_column_code = 'enerc'""",
    )
    assert energy[0] == 1491
    assert abs(energy[1] - 1491 / 4.18) < 0.01
    assert abs(energy[2] - 15 / 4.18) < 0.0001

    calcium = _one(
        ifct_db,
        """SELECT fn.value_native, fn.value_canonical, fn.sd FROM food_nutrients fn
           JOIN nutrients n ON n.id = fn.nutrient_id JOIN foods f ON f.id = fn.food_id
           WHERE f.source_code = 'A015' AND n.ifct_column_code = 'ca'""",
    )
    assert abs(calcium[1] - calcium[0] * 1000) < 0.0001
    assert abs(calcium[2] - 1.26) < 0.0001


def test_language_codes_are_mapped():
    assert extract_regional_names("H. Bajra; Tam. Kambu") == {
        "Hindi": "Bajra",
        "Tamil": "Kambu",
    }


def test_food_states_are_derived_from_sections(ifct_db):
    assert _one(ifct_db, "SELECT COUNT(*) FROM foods WHERE source_code LIKE 'M%' AND food_state = 'COOKED'")[0] > 0
    assert _one(ifct_db, "SELECT COUNT(*) FROM foods WHERE source_code LIKE 'M%' AND food_state = 'RAW'")[0] > 0
    assert _one(ifct_db, "SELECT COUNT(*) FROM foods WHERE source_code LIKE 'N%' AND food_state = 'UNKNOWN'")[0] == 19
