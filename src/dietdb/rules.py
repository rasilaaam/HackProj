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
    for item in json.loads((seed_dir / "patient_variables.json").read_text()):
        conn.execute(
            """INSERT OR REPLACE INTO patient_variables
               (variable_name, display_name, data_type, unit, min_value, max_value, source, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (item["variable_name"], item["display_name"], item["data_type"], item.get("unit"),
             item.get("min_value"), item.get("max_value"), item["source"], item["range_note"]),
        )


def load_rules(db_path: str | Path, rules_dir: str | Path, mode: str = "production") -> int:
    if mode not in {"production", "test"}:
        raise ValueError("mode must be production or test")
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
                if rule.status.value != "APPROVED" and not (mode == "test" and rule.status.value == "TEST_FIXTURE"):
                    raise ValueError(f"rule {rule.slug} has status {rule.status.value}, not loadable in {mode} mode")
                _validate_expression(rule.applies_when, variables)
                _validate_target(conn, rule)
                data = rule.model_dump(mode="json")
                columns = ["slug", "name", "kind", "target_type", "target_ref", "min_value", "max_value",
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
