"""Validated loading of declarative diet rules."""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from dietdb.models_rules import Rule

OPS = {"<", "<=", ">", ">=", "==", "!=", "in"}


def _validate_expression(expr: Any, variables: set[str]) -> None:
    if not isinstance(expr, dict):
        raise ValueError("applies_when must be a declarative expression object")
    if "and" in expr or "or" in expr:
        children = expr.get("and", expr.get("or"))
        if not isinstance(children, list) or not children:
            raise ValueError("and/or expressions require a non-empty list")
        for child in children:
            _validate_expression(child, variables)
        return
    if "not" in expr:
        _validate_expression(expr["not"], variables)
        return
    if "var" not in expr or expr.get("op") not in OPS or "value" not in expr:
        raise ValueError("variable expressions require var, op, and value")
    if expr["var"] not in variables:
        raise ValueError(f"unknown patient variable: {expr['var']}")


def _validate_target(conn, rule: Rule) -> None:
    table = {
        "NUTRIENT": ("nutrients", "canonical_name"),
        "FOOD": ("foods", "source_code"),
        "FOOD_GROUP": ("food_groups", "code"),
        "ALLERGEN": ("allergens", "code"),
    }.get(rule.target_type.value)
    if table is None:
        return
    found = conn.execute(
        f"SELECT 1 FROM {table[0]} WHERE {table[1]} = ?", (rule.target_ref,)
    ).fetchone()
    if found is None:
        raise ValueError(f"unknown {rule.target_type.value.lower()} target: {rule.target_ref}")


def seed_reference_data(conn, seed_dir: Path) -> None:
    for item in json.loads((seed_dir / "allergens.json").read_text()):
        conn.execute(
            "INSERT OR IGNORE INTO allergens(code, name, description) VALUES (?, ?, ?)",
            (item["code"], item["name"], item["description"]),
        )
    variable_items = json.loads((seed_dir / "patient_variables.json").read_text())
    extra = seed_dir / "patient_variables_conditions.json"
    if extra.exists():
        variable_items.extend(json.loads(extra.read_text()))
    for item in variable_items:
        conn.execute(
            """INSERT OR REPLACE INTO patient_variables
               (variable_name, display_name, data_type, unit, min_value, max_value, source, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (item["variable_name"], item["display_name"], item["data_type"], item.get("unit"),
             item.get("min_value"), item.get("max_value"), item["source"], item.get("range_note")),
        )


def load_rules(db_path: str | Path, rules_dir: str | Path, mode: str = "production") -> int:
    if mode not in {"production", "test", "draft-review"}:
        raise ValueError("mode must be production, test, or draft-review")
    conn = __import__("sqlite3").connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    root = Path(__file__).resolve().parents[2]
    seed_reference_data(conn, root / "data/seed")
    variables = {r[0] for r in conn.execute("SELECT variable_name FROM patient_variables")}
    loaded = 0
    try:
        for path in sorted(Path(rules_dir).glob("*.json")):
            items = json.loads(path.read_text())
            if isinstance(items, dict):
                items = [items]
            for raw in items:
                try:
                    rule = Rule.model_validate(raw)
                except ValidationError as exc:
                    raise ValueError(f"invalid rule in {path.name}: {exc}") from exc
                allowed = rule.status.value == "APPROVED" or (mode == "test" and rule.status.value == "TEST_FIXTURE") or (mode == "draft-review" and rule.status.value == "DRAFT")
                if not allowed:
                    raise ValueError(f"rule {rule.slug} has status {rule.status.value}, not loadable in {mode} mode")
                _validate_expression(rule.applies_when, variables)
                for variable in (rule.min_from_variable, rule.max_from_variable):
                    if variable and variable not in variables:
                        raise ValueError(f"unknown patient variable: {variable}")
                _validate_target(conn, rule)
                data = rule.model_dump(mode="json")
                columns = ["slug", "name", "kind", "target_type", "target_ref", "min_value", "max_value", "min_from_variable", "max_from_variable",
                           "target_value", "tolerance", "unit", "basis", "tier", "enforcement", "applies_when",
                           "rationale", "source_id", "source_locator", "evidence_grade", "status", "version"]
                values = [json.dumps(data["applies_when"]) if c == "applies_when" else data.get(c) for c in columns]
                conn.execute(
                    f"INSERT OR REPLACE INTO rules ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                    values,
                )
                loaded += 1
        conn.commit()
        return loaded
    finally:
        conn.close()


def load_conditions(db_path: str | Path, conditions_path: str | Path) -> int:
    """Load draft condition metadata and validate every selector expression."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    root = Path(__file__).resolve().parents[2]
    seed_reference_data(conn, root / "data/seed")
    variables = {r[0] for r in conn.execute("SELECT variable_name FROM patient_variables")}
    loaded = 0
    try:
        for item in json.loads(Path(conditions_path).read_text()):
            expression = item.get("eligibility_expression")
            if isinstance(expression, str):
                expression = json.loads(expression)
            if expression:
                _validate_expression(expression, variables)
            conn.execute("""INSERT OR REPLACE INTO conditions
                (slug, name, icd10_code, category, chronicity, planning_mode,
                 review_interval_months, eligibility_expression, description, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                item["slug"], item["name"], item.get("icd10_code"), item["category"],
                item["chronicity"], item["planning_mode"], item.get("review_interval_months"),
                json.dumps(expression) if expression else None, item.get("description"), item.get("status", "DRAFT")))
            condition_id = conn.execute("SELECT id FROM conditions WHERE slug = ?", (item["slug"],)).fetchone()[0]
            for profile in item.get("profiles", []):
                selector = profile["selector_expression"]
                if isinstance(selector, str): selector = json.loads(selector)
                _validate_expression(selector, variables)
                conn.execute("""INSERT OR REPLACE INTO condition_profiles
                    (condition_id, slug, name, stage_or_variant, selector_expression,
                     exclusivity_group, priority, planning_mode_override)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (
                    condition_id, profile["slug"], profile["name"], profile.get("stage_or_variant"),
                    json.dumps(selector), profile.get("exclusivity_group"), profile.get("priority", 0),
                    profile.get("planning_mode_override")))
            loaded += 1
        conn.commit()
        return loaded
    finally:
        conn.close()
