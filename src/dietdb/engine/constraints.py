"""Patient validation and deterministic rule resolution for E1."""
import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from pydantic import BaseModel
from dietdb.engine.db import connect_readonly


class Patient(BaseModel):
    values: dict[str, Any]

    @classmethod
    def from_database(cls, values: dict[str, Any], db: str) -> "Patient":
        conn = connect_readonly(db)
        definitions = {r[0]: r for r in conn.execute("SELECT variable_name, data_type, allowed_values, min_value, max_value FROM patient_variables")}
        conn.close()
        unknown = set(values) - set(definitions)
        if unknown:
            raise ValueError(f"unknown patient variables: {', '.join(sorted(unknown))}")
        for name, value in values.items():
            _, data_type, allowed, minimum, maximum = definitions[name]
            if data_type in {"INTEGER", "REAL"} and (not isinstance(value, (int, float)) or isinstance(value, bool)):
                raise ValueError(f"patient value for {name} must be numeric")
            if minimum is not None and value < minimum or maximum is not None and value > maximum:
                raise ValueError(f"patient value outside plausibility range: {name}")
            if data_type == "BOOLEAN" and value not in {True, False, 0, 1}:
                raise ValueError(f"patient value for {name} must be boolean")
            if data_type == "ENUM" and allowed and str(value).casefold() not in {str(x).casefold() for x in json.loads(allowed)}:
                raise ValueError(f"invalid value for patient variable: {name}")
        return cls(values=values)


@dataclass
class ResolvedConstraints:
    status: str = "OK"
    planning_mode: str = "AUTO_PLAN"
    nutrients: dict[str, dict[str, Any]] = field(default_factory=dict)
    allergen_exclusions: set[str] = field(default_factory=set)
    food_exclusions: set[str] = field(default_factory=set)
    advisories: list[dict[str, Any]] = field(default_factory=list)
    needs_info: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    energy_target_kcal: float | None = None
    applied_rules: list[dict[str, Any]] = field(default_factory=list)


def _eval(expr: dict, values: dict[str, Any], missing: set[str]) -> bool | None:
    if "and" in expr:
        results = [_eval(x, values, missing) for x in expr["and"]]
        return False if False in results else (None if None in results else True)
    if "or" in expr:
        results = [_eval(x, values, missing) for x in expr["or"]]
        return True if True in results else (None if None in results else False)
    if "not" in expr:
        result = _eval(expr["not"], values, missing)
        return None if result is None else not result
    variable = expr["var"]
    if variable not in values:
        missing.add(variable)
        return None
    actual, expected, op = values[variable], expr["value"], expr["op"]
    if op == "in":
        return actual in expected
    try:
        return {"<": actual < expected, "<=": actual <= expected, ">": actual > expected,
                ">=": actual >= expected, "==": actual == expected, "!=": actual != expected}[op]
    except TypeError as exc:
        raise ValueError(f"cannot compare patient variable {variable} with rule value") from exc


def _energy(values: dict[str, Any]) -> float | None:
    if "energy_target_kcal" in values:
        return float(values["energy_target_kcal"])
    required = {"sex", "age_years", "weight_kg", "height_cm", "activity_level"}
    if not required <= values.keys():
        return None
    factors = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "very active": 1.9}
    activity = str(values["activity_level"]).lower()
    if activity not in factors:
        raise ValueError(f"unknown activity level: {values['activity_level']}")
    base = 10 * values["weight_kg"] + 6.25 * values["height_cm"] - 5 * values["age_years"]
    base += 5 if str(values["sex"]).lower() in {"male", "m"} else -161
    return base * factors[activity]


def _converted(rule: dict[str, Any], patient: dict[str, Any], energy: float | None) -> tuple[float | None, float | None] | str:
    basis = rule["basis"]
    if basis == "PER_DAY":
        factor = 1.0
    elif basis == "PER_KG_ACTUAL_WEIGHT":
        if "weight_kg" not in patient: return "weight_kg"
        factor = float(patient["weight_kg"])
    elif basis == "PER_1000_KCAL":
        if energy is None: return "energy_target_kcal"
        factor = energy / 1000.0
    elif basis == "PCT_OF_ENERGY":
        if energy is None: return "energy_target_kcal"
        kcal_per_gram = {"protein": 4.0, "carbohydrate": 4.0, "fat": 9.0, "fat_total": 9.0}.get(rule["target_ref"])
        if kcal_per_gram is None: return "unsupported PCT_OF_ENERGY target"
        factor = energy / (100.0 * kcal_per_gram)
    else:
        return f"UNSUPPORTED_BASIS:{basis}"
    values = {}
    for key in ("min", "max"):
        variable = rule.get(f"{key}_from_variable")
        raw = patient.get(variable) if variable else rule.get(f"{key}_value")
        if variable and variable not in patient: return variable
        values[key] = None if raw is None else float(raw) * factor
    return values["min"], values["max"]


def resolve(patient: Patient, db: str, mode: str = "production") -> ResolvedConstraints:
    conn = connect_readonly(db)
    columns = [d[0] for d in conn.execute("SELECT * FROM rules LIMIT 0").description]
    rows = conn.execute("""SELECT * FROM rules WHERE status = 'APPROVED'
        OR (? IN ('test', 'draft-review') AND status IN ('TEST_FIXTURE', 'DRAFT'))""", (mode,)).fetchall()
    result = ResolvedConstraints(energy_target_kcal=_energy(patient.values))
    groups: dict[str, dict[str, list[tuple[dict[str, Any], float | None, float | None]]]] = {}
    for raw in rows:
        rule = dict(zip(columns, raw))
        missing: set[str] = set()
        outcome = _eval(json.loads(rule["applies_when"]), patient.values, missing)
        if outcome is None:
            result.needs_info.append({"rule": rule["slug"], "variables": sorted(missing)})
            if rule["enforcement"] in {"HARD", "SOFT"} or rule["tier"] == "SAFETY_CRITICAL": result.status = "INCOMPLETE"
            continue
        if not outcome: continue
        result.applied_rules.append({"slug": rule["slug"], "rationale": rule["rationale"],
                                     "source_locator": rule["source_locator"], "target_ref": rule["target_ref"]})
        if rule["slug"].startswith("ckd_dialysis"):
            result.planning_mode, result.status = "CLINICIAN_ONLY_NO_AUTOPLAN", "CLINICIAN_REQUIRED"
        target = rule["target_ref"]
        if rule["enforcement"] == "ADVISORY" or rule["target_type"] != "NUTRIENT":
            result.advisories.append({"rule": rule["slug"], "target": target, "rationale": rule["rationale"]})
            if rule["target_type"] == "ALLERGEN": result.allergen_exclusions.add(target)
            if rule["target_type"] == "FOOD": result.food_exclusions.add(target)
            continue
        converted = _converted(rule, patient.values, result.energy_target_kcal)
        if isinstance(converted, str):
            reason = converted
            result.needs_info.append({"rule": rule["slug"], "variables": [] if reason.startswith(("UNSUPPORTED", "unsupported")) else [reason], "reason": reason})
            result.status = "INCOMPLETE"
            continue
        minimum, maximum = converted
        cls = "HARD" if rule["enforcement"] == "HARD" or rule["tier"] == "SAFETY_CRITICAL" else "SOFT"
        groups.setdefault(target, {}).setdefault(cls, []).append((rule, minimum, maximum))
    for target, classes in groups.items():
        resolved: dict[str, Any] = {"min": None, "max": None, "rules": []}
        bounds: dict[str, dict[str, Any]] = {}
        for cls, entries in classes.items():
            preferred = [x for x in entries if x[0]["tier"] in {"THERAPEUTIC", "SAFETY_CRITICAL"}]
            entries = preferred or entries
            minimum = max((x[1] for x in entries if x[1] is not None), default=None)
            maximum = min((x[2] for x in entries if x[2] is not None), default=None)
            names = [x[0]["slug"] for x in entries]
            bounds[cls] = {"min": minimum, "max": maximum, "rules": names}
            if minimum is not None and maximum is not None and minimum > maximum:
                result.status = "INFEASIBLE_RULES"
                result.conflicts.append({"nutrient": target, "rules": names, "rationales": [x[0]["rationale"] for x in entries]})
        if "HARD" in bounds: resolved.update(bounds["HARD"]); resolved["hard"] = bounds["HARD"]
        if "SOFT" in bounds:
            resolved["soft"] = bounds["SOFT"]
            if "HARD" in bounds:
                resolved["overridden_by_hard"] = bounds["SOFT"]["rules"]
                result.advisories.extend({"rule": name, "reason": "OVERRIDDEN_BY_HARD"} for name in bounds["SOFT"]["rules"])
            else: resolved.update(bounds["SOFT"])
        result.nutrients[target] = resolved
    conn.close()
    return result
