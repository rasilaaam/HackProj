"""End-to-end tests for the planning engine (draft rules, no language model)."""
import copy
import json
import sqlite3
from pathlib import Path

import pytest

from dietdb.__main__ import build_database
from dietdb.curated.allergens import classify
from dietdb.engine.planner import dumps, make_plan
from dietdb.engine.verifier import verify
from dietdb.engine.constraints import Patient, resolve
from dietdb.engine.optimizer import load_template
from dietdb.rules import load_conditions, load_rules

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests/fixtures"


@pytest.fixture(scope="session")
def review_db(tmp_path_factory):
    db = tmp_path_factory.mktemp("engine") / "review.db"
    build_database(str(db))
    load_rules(str(db), ROOT / "data/rules/draft", "draft-review")
    load_conditions(str(db), ROOT / "data/conditions/draft_conditions.json")
    return str(db)


def fixture(name):
    return json.loads((FIX / f"{name}.json").read_text())


def test_allergen_classification_identity_rules():
    assert classify("Ground nut", "H")[0] == {"peanuts"}
    assert "gluten_cereals" in classify("Wheat flour, atta", "A")[0]
    assert classify("Rice, raw, milled", "A") == (set(), set())
    assert classify("Milk, whole, Cow", "L")[0] == {"milk"}
    assert "sesame" in classify("Gingelly seeds, white", "H")[0]
    assert classify("Coconut, kernel, fresh", "H")[1] == {"tree_nuts"}


def test_all_foods_have_a_tag_for_every_allergen(review_db):
    conn = sqlite3.connect(review_db)
    foods = conn.execute("SELECT count(*) FROM foods").fetchone()[0]
    allergens = conn.execute("SELECT count(*) FROM allergens").fetchone()[0]
    assert conn.execute("SELECT count(*) FROM food_allergens").fetchone()[0] == foods * allergens


def test_ckd_with_clinician_limits_gets_verified_plan_within_limits(review_db):
    out = make_plan(review_db, {**fixture("ckd_g3b_t2d"), "allergy_list": []}, "draft-review")
    assert out["status"] == "OK" and out["verification"]["ok"]
    totals = out["verification"]["totals"]
    assert totals["potassium"] <= 2500 and totals["phosphorus"] <= 900 and totals["sodium"] <= 2300
    assert totals["protein"] <= 0.8 * 75 + 1
    assert out["banner"].startswith("RULES ARE UNREVIEWED DRAFTS")


def test_ckd_without_clinician_limit_is_incomplete_and_names_variables(review_db):
    out = make_plan(review_db, {**fixture("ckd_without_clinician_limits"), "allergy_list": []}, "draft-review")
    assert out["status"] == "INCOMPLETE" and "plan" not in out
    names = {v for n in out["needs_info"] for v in n["variables"]}
    assert {"clinician_max_potassium_mg_day", "clinician_max_phosphorus_mg_day"} <= names


def test_dialysis_requires_clinician(review_db):
    out = make_plan(review_db, {**fixture("dialysis"), "allergy_list": []}, "draft-review")
    assert out["status"] == "CLINICIAN_REQUIRED" and "plan" not in out


def test_impossible_limits_give_diagnosis_not_a_plan(review_db):
    values = {**fixture("ckd_g3b_t2d"), "allergy_list": [], "clinician_max_potassium_mg_day": 300, "clinician_max_phosphorus_mg_day": 100}
    out = make_plan(review_db, values, "draft-review")
    assert out["status"] == "INFEASIBLE_PLAN" and "plan" not in out
    assert any("phosphorus" in g["constraint"] for g in out["diagnostics"]["would_need_to_relax"])


def test_missing_allergy_list_is_incomplete(review_db):
    values = {k: v for k, v in fixture("ckd_g3b_t2d").items() if k != "allergy_list"}
    assert make_plan(review_db, values, "draft-review")["status"] == "INCOMPLETE"


def test_production_mode_without_approved_rules_refuses(review_db):
    out = make_plan(review_db, {**fixture("ckd_g3b_t2d"), "allergy_list": []}, "production")
    assert out["status"] == "INCOMPLETE" and "no rules are loaded" in out["message"]


def test_allergens_and_diet_pattern_are_respected(review_db):
    values = {**fixture("ckd_g3b_t2d"), "allergy_list": ["peanuts", "milk", "gluten_cereals"], "dietary_pattern": "vegan"}
    out = make_plan(review_db, values, "draft-review")
    assert out["status"] == "OK" and out["verification"]["ok"]
    names = {i["name"] for s in out["plan"]["slots"].values() for i in s}
    assert not names & {"Ground nut", "Paneer", "Wheat flour, atta", "Wheat, whole", "Milk, whole, Cow", "Wheat, semolina"}


def test_plan_output_is_byte_identical_on_repeat(review_db):
    values = {**fixture("ckd_g3b_t2d"), "allergy_list": []}
    assert dumps(make_plan(review_db, values, "draft-review")) == dumps(make_plan(review_db, values, "draft-review"))


def test_salt_is_reserved_inside_the_sodium_bound(review_db):
    out = make_plan(review_db, {**fixture("ckd_g3b_t2d"), "allergy_list": []}, "draft-review")
    salt_mg = out["plan"]["sodium_total_includes_added_salt_mg"]
    assert salt_mg > 0 and out["verification"]["totals"]["sodium"] <= 2300
    assert out["verification"]["bounds"]["sodium"]["total"] == out["verification"]["totals"]["sodium"]


def _plan_inputs(review_db):
    values = {**fixture("ckd_g3b_t2d"), "allergy_list": ["peanuts"], "dietary_pattern": "vegetarian"}
    out = make_plan(review_db, values, "draft-review")
    resolved = resolve(Patient.from_database(values, review_db), review_db, "draft-review")
    body = {"items": [dict(slot=s, **i) for s, items in out["plan"]["slots"].items() for i in items], "salt_g": out["plan"]["added_salt_allowance_g"]}
    return out, resolved, body, values


def _verify(review_db, body, resolved, values, **kw):
    template = load_template(ROOT / "data/templates/meal_templates.json")
    return verify(review_db, body, resolved.nutrients, resolved.energy_target_kcal, template, ["peanuts"], "vegetarian",
                  kw.get("salt_min", 1.0), kw.get("salt_max", 5.0))


def test_verifier_accepts_the_valid_plan(review_db):
    out, resolved, body, values = _plan_inputs(review_db)
    assert _verify(review_db, body, resolved, values)["ok"]


def test_verifier_catches_added_high_potassium_food(review_db):
    out, resolved, body, values = _plan_inputs(review_db)
    conn = sqlite3.connect(review_db)
    fid = conn.execute("SELECT id FROM foods WHERE english_name = 'Banana, ripe, robusta'").fetchone()[0]
    bad = copy.deepcopy(body)
    bad["items"].append({"slot": "snack", "food_id": fid, "source_code": "X", "name": "Banana", "group": "E", "grams": 250, "approximate": False})
    result = _verify(review_db, bad, resolved, values)
    assert not result["ok"] and any(v["check"] in ("HARD_MAX", "PER_FOOD_CAP", "SLOT_GROUP_RANGE") for v in result["violations"])


def test_verifier_catches_allergen_food(review_db):
    out, resolved, body, values = _plan_inputs(review_db)
    conn = sqlite3.connect(review_db)
    fid = conn.execute("SELECT id FROM foods WHERE english_name = 'Ground nut'").fetchone()[0]
    bad = copy.deepcopy(body)
    bad["items"].append({"slot": "snack", "food_id": fid, "source_code": "H012", "name": "Ground nut", "group": "H", "grams": 20, "approximate": False})
    assert any(v["check"] == "ALLERGEN" for v in _verify(review_db, bad, resolved, values)["violations"])


def test_verifier_catches_tampered_grams_and_missing_salt(review_db):
    out, resolved, body, values = _plan_inputs(review_db)
    bad = copy.deepcopy(body)
    for it in bad["items"]: it["grams"] = it["grams"] * 3
    assert not _verify(review_db, bad, resolved, values)["ok"]
    no_salt = {**body, "salt_g": 9.0}
    assert any(v["check"] == "SALT_RANGE" for v in _verify(review_db, no_salt, resolved, values)["violations"])
