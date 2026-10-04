import json

import pytest

from dietdb.db import DatabaseManager
from dietdb.llm import explain, extract_patient
from dietdb.rules import seed_reference_data


class FakeModel:
    def __init__(self, payload=None, text=""):
        self.payload = payload
        self.text = text

    def generate_json(self, prompt):
        return self.payload

    def generate_text(self, prompt):
        return self.text


class RaisingModel:
    def generate_json(self, prompt):
        raise TimeoutError("fake timeout")

    def generate_text(self, prompt):
        raise OSError("fake network error")


@pytest.fixture
def patient_db(tmp_path):
    db = tmp_path / "llm.db"
    DatabaseManager(db).init_db()
    import sqlite3
    conn = sqlite3.connect(db)
    seed_reference_data(conn, __import__("pathlib").Path(__file__).parent.parent / "data/seed")
    conn.commit()
    conn.close()
    return db


def test_extraction_drops_unknown_and_rejects_invalid_values(patient_db):
    result = extract_patient("report", patient_db, FakeModel({"age_years": 45, "not_a_field": 2, "weight_kg": -4}))
    assert result["values"] == {"age_years": 45}
    assert result["unknown_fields"] == ["not_a_field"]
    assert result["rejected_fields"][0]["field"] == "weight_kg"


def test_extraction_reports_missing_fields(patient_db):
    result = extract_patient("report", patient_db, FakeModel({"age_years": 45}))
    assert "weight_kg" in result["missing_fields"]


def test_explanation_discards_invented_number():
    payload = {"status": "OK", "energy_total_kcal": 1200, "rules_applied": [{"rationale": "Keep energy near the target."}]}
    result = explain(payload, model=FakeModel(text="The plan provides 1200 kcal and 9999 mg."))
    assert result == "Keep energy near the target."


def test_model_errors_fail_closed(patient_db):
    extracted = extract_patient("report", patient_db, RaisingModel())
    assert extracted["skipped"] is True and extracted["error"] == "fake timeout"
    payload = {"rules_applied": [{"rationale": "Use the supplied plan bounds."}]}
    assert explain(payload, model=RaisingModel()) == "Use the supplied plan bounds."
