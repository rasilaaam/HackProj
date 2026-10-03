import sqlite3
from pathlib import Path

from dietdb.engine.constraints import Patient, resolve
from dietdb.rules import load_rules
ROOT = Path(__file__).parent.parent


def test_e1_resolves_fixture_rule(tmp_path):
    db = tmp_path / "constraints.db"
    from dietdb.db import DatabaseManager
    DatabaseManager(db).init_db()
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO nutrients(canonical_name,display_name,category,canonical_unit) VALUES('protein','Protein','MACRONUTRIENT','g')")
    conn.commit(); conn.close()
    load_rules(db, ROOT / "data/rules", "test")
    patient = Patient.from_database({"age_years": 30}, str(db))
    resolved = resolve(patient, str(db), "test")
    assert resolved.status == "OK"
    assert resolved.nutrients["protein"]["max"] == 100


def test_e1_rejects_unknown_patient_variable(tmp_path):
    from dietdb.db import DatabaseManager
    db = tmp_path / "patient.db"
    DatabaseManager(db).init_db()
    try:
        Patient.from_database({"not_a_variable": 1}, str(db))
        assert False
    except ValueError as exc:
        assert "unknown patient" in str(exc)
