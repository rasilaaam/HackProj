"""Patient validation and deterministic rule resolution for E1."""

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


class Patient(BaseModel):
    values: dict[str, Any]

    @classmethod
    def from_database(cls, values: dict[str, Any], db: str) -> "Patient":
        conn = sqlite3.connect(db)
        definitions = {r[0]: r for r in conn.execute(
            "SELECT variable_name, data_type, allowed_values, min_value, max_value FROM patient_variables"
        )}
        conn.close()
        unknown = set(values) - set(definitions)
        if unknown:
            raise ValueError(f"unknown patient variables: {', '.join(sorted(unknown))}")
        for name, value in values.items():
            _, data_type, allowed, minimum, maximum = definitions[name]
            if minimum is not None and value < minimum or maximum is not None and value > maximum:
                raise ValueError(f"patient value outside plausibility range: {name}")
            if data_type == "ENUM" and allowed and value not in json.loads(allowed):
                raise ValueError(f"invalid value for patient variable: {name}")
        return cls(values=values)


@dataclass
class ResolvedConstraints:
    status: str = "OK"
    nutrients: dict[str, dict[str, Any]] = field(default_factory=dict)
    allergen_exclusions: set[str] = field(default_factory=set)
    food_exclusions: set[str] = field(default_factory=set)
    needs_info: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    energy_target_kcal: float | None = None


def _eval(expr: dict, values: dict[str, Any]) -> bool | None:
    if "and" in expr:
        results = [_eval(x, values) for x in expr["and"]]
        return False if False in results else (None if None in results else True)
    if "or" in expr:
        results = [_eval(x, values) for x in expr["or"]]
        return True if True in results else (None if None in results else False)
    if "not" in expr:
        result = _eval(expr["not"], values)
        return None if result is None else not result
    variable = expr["var"]
    if variable not in values:
        return None
    actual, expected, op = values[variable], expr["value"], expr["op"]
    if op == "in": return actual in expected
    return {"<": actual < expected, "<=": actual <= expected, ">": actual > expected,
            ">=": actual >= expected, "==": actual == expected, "!=": actual != expected}[op]


def _energy(values: dict[str, Any]) -> float | None:
    required = {"sex", "age_years", "weight_kg", "height_cm", "activity_level"}
    if not required <= values.keys():
        return None
    base = 10 * values["weight_kg"] + 6.25 * values["height_cm"] - 5 * values["age_years"]
    base += 5 if str(values["sex"]).lower() in {"male", "m"} else -161
    factors = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "very active": 1.9}
    return base * factors[str(values["activity_level"]).lower()]


def resolve(patient: Patient, db: str, mode: str = "production") -> ResolvedConstraints:
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT * FROM rules WHERE status = 'APPROVED' OR (? = 'test' AND status = 'TEST_FIXTURE')", (mode,)).fetchall()
    columns = [d[0] for d in conn.execute("SELECT * FROM rules LIMIT 0").description]
    result = ResolvedConstraints(energy_target_kcal=_energy(patient.values))
    selected = {}
    for raw in rows:
        rule = dict(zip(columns, raw))
        outcome = _eval(json.loads(rule["applies_when"]), patient.values)
        if outcome is None:
            result.needs_info.append({"rule": rule["slug"], "variables": []})
            if rule["enforcement"] == "HARD" or rule["tier"] == "SAFETY_CRITICAL": result.status = "INCOMPLETE"
            continue
        if not outcome: continue
        target = rule["target_ref"]
        if rule["target_type"] == "ALLERGEN": result.allergen_exclusions.add(target); continue
        if rule["target_type"] == "FOOD": result.food_exclusions.add(target); continue
        if rule["target_type"] != "NUTRIENT": continue
        if rule["basis"] == "PER_KG_ACTUAL_WEIGHT":
            if "weight_kg" not in patient.values:
                result.needs_info.append({"rule": rule["slug"], "variables": ["weight_kg"]}); result.status = "INCOMPLETE"; continue
            factor = patient.values["weight_kg"]
        elif rule["basis"] == "PER_DAY": factor = 1
        elif rule["basis"] == "PER_1000_KCAL":
            if result.energy_target_kcal is None: result.needs_info.append({"rule": rule["slug"], "variables": ["energy_target_kcal"]}); result.status = "INCOMPLETE"; continue
            factor = result.energy_target_kcal / 1000
        elif rule["basis"] == "PCT_OF_ENERGY":
            if result.energy_target_kcal is None: result.needs_info.append({"rule": rule["slug"], "variables": ["energy_target_kcal"]}); result.status = "INCOMPLETE"; continue
            factor = result.energy_target_kcal / 100
        else:
            result.needs_info.append({"rule": rule["slug"], "variables": [], "reason": "UNSUPPORTED_BASIS"}); result.status = "INCOMPLETE"; continue
        rank = {"BASELINE_DEFAULT": 0, "THERAPEUTIC": 1, "SAFETY_CRITICAL": 2}[rule["tier"]]
        if target in selected and rank < selected[target][0]: continue
        selected[target] = (rank, rule, factor)
    for target, (_, rule, factor) in selected.items():
        item = result.nutrients.setdefault(target, {"min": None, "max": None, "rules": []})
        item["min"] = None if rule["min_value"] is None else rule["min_value"] * factor
        item["max"] = None if rule["max_value"] is None else rule["max_value"] * factor
        item["rules"].append(rule["slug"])
        if item["min"] is not None and item["max"] is not None and item["min"] > item["max"]:
            result.status = "INFEASIBLE_RULES"; result.conflicts.append({"rule": rule["slug"], "rationale": rule["rationale"]})
    conn.close()
    return result
