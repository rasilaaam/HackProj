"""Deterministic linear optimizer for raw edible food portions."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linprog


SALT_SODIUM_MG_PER_G = 393.0


def _allergy_codes(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [x.strip() for x in value.split(",") if x.strip()]
    return {str(x) for x in value}


def _foods(conn: sqlite3.Connection, patient: dict[str, Any], resolved: Any) -> list[dict[str, Any]]:
    rows = conn.execute("""SELECT f.id, f.source_code, f.english_name, f.food_group_id
        FROM foods f ORDER BY f.id""").fetchall()
    allergy_codes = _allergy_codes(patient.get("allergy_list"))
    excluded = set(resolved.food_exclusions)
    diet = patient.get("dietary_pattern")
    candidates = []
    hard_upper = {n for n, b in resolved.nutrients.items()
                  if b.get("max") is not None and ("hard" in b or not b.get("soft"))}
    for food_id, source_code, name, group_id in rows:
        if source_code in excluded:
            continue
        if allergy_codes:
            placeholders = ",".join("?" * len(allergy_codes))
            found = conn.execute(f"""SELECT 1 FROM food_allergens fa JOIN allergens a ON a.id=fa.allergen_id
                WHERE fa.food_id=? AND a.code IN ({placeholders}) AND fa.presence IN ('PRESENT','UNKNOWN') LIMIT 1""",
                [food_id, *sorted(allergy_codes)]).fetchone()
            if found:
                continue
        if diet:
            compatible = conn.execute("""SELECT 1 FROM diet_type_tags dt JOIN diet_types d ON d.id=dt.diet_type_id
                WHERE dt.food_id=? AND d.code=? AND dt.is_compatible=1 LIMIT 1""", (food_id, diet)).fetchone()
            if compatible is None:
                continue
        values = {r[0]: r[1:] for r in conn.execute("""SELECT n.canonical_name, fn.value_canonical,
            fn.value_status FROM food_nutrients fn JOIN nutrients n ON n.id=fn.nutrient_id WHERE fn.food_id=?""", (food_id,))}
        if any(n not in values or values[n][0] is None or values[n][1] == "NOT_ANALYSED" for n in hard_upper):
            continue
        approximate = any(v[1] == "NOT_DETECTED" for v in values.values())
        candidates.append({"id": food_id, "source_code": source_code, "name": name,
                           "food_group_id": group_id, "values": values, "approximate": approximate})
    return candidates


def _templates(path: Path | None) -> list[dict[str, Any]]:
    if path and path.exists():
        return json.loads(path.read_text())["slots"]
    return [{"slot": "any", "min_grams": 0, "max_grams": 10000}]


def optimize(db: str | Path, patient: dict[str, Any], resolved: Any,
             added_salt_g_per_day: float = 5.0, template_path: str | Path | None = None) -> dict[str, Any]:
    """Return a deterministic plan, never claiming success for an unverified LP."""
    conn = sqlite3.connect(str(db))
    candidates = _foods(conn, patient, resolved)
    if not candidates:
        conn.close()
        return {"status": "INFEASIBLE_PLAN", "foods": [], "slots": [], "nutrients": {},
                "needs_info": [{"reason": "no eligible candidate foods"}]}
    nutrients = sorted(resolved.nutrients)
    n = len(candidates)
    energy = resolved.energy_target_kcal
    c = np.array([1.0 + i * 1e-8 for i in range(n)], dtype=float)
    a_ub: list[list[float]] = []
    b_ub: list[float] = []
    labels: list[str] = []
    soft_ub: list[list[float]] = []
    soft_b: list[float] = []
    soft_labels: list[str] = []
    for nutrient in nutrients:
        values = np.array([0.0 if f["values"].get(nutrient, (None,))[0] is None else
                           (f["values"][nutrient][0] or 0.0) / 100.0 for f in candidates])
        bound = resolved.nutrients[nutrient]
        hard_bound = bound if "hard" in bound else None
        active = hard_bound or (None if "soft" in bound else bound)
        for target, matrix, rhs, name in ((active, a_ub, b_ub, labels),):
            if target is None: continue
            maximum = target.get("max")
            if nutrient == "sodium" and maximum is not None:
                maximum -= SALT_SODIUM_MG_PER_G * added_salt_g_per_day
            if maximum is not None:
                matrix.append(values.tolist()); rhs.append(float(maximum)); name.append(f"{nutrient}:max")
            minimum = target.get("min")
            if minimum is not None:
                matrix.append((-values).tolist()); rhs.append(-float(minimum)); name.append(f"{nutrient}:min")
        soft = bound.get("soft")
        if soft:
            for maximum, minimum in ((soft.get("max"), soft.get("min")),):
                if maximum is not None:
                    soft_ub.append(values.tolist()); soft_b.append(float(maximum)); soft_labels.append(f"{nutrient}:soft:max")
                if minimum is not None:
                    soft_ub.append((-values).tolist()); soft_b.append(-float(minimum)); soft_labels.append(f"{nutrient}:soft:min")
    if energy is not None:
        values = np.array([(f["values"].get("energy_kcal", (0.0,))[0] or 0.0) / 100.0 for f in candidates])
        a_ub.append(values.tolist()); b_ub.append(float(energy * 1.2)); labels.append("energy:max")
        a_ub.append((-values).tolist()); b_ub.append(-float(energy * 0.8)); labels.append("energy:min")
    bounds = [(0.0, 10000.0)] * n
    result = linprog(c, A_ub=np.array(a_ub + soft_ub) if a_ub or soft_ub else None,
                     b_ub=np.array(b_ub + soft_b) if b_ub or soft_b else None,
                     bounds=bounds, method="highs", options={"presolve": True})
    relaxed: list[dict[str, Any]] = []
    if not result.success:
        # Add one non-negative slack variable per SOFT row. The large penalty
        # preserves the hard feasible region while preferring small violations.
        if soft_ub:
            total = n + len(soft_ub)
            objective = np.r_[c, np.full(len(soft_ub), 100000.0)]
            matrix = []
            rhs = list(b_ub)
            for row, value in zip(a_ub, b_ub):
                matrix.append(row + [0.0] * len(soft_ub))
            for i, (row, value) in enumerate(zip(soft_ub, soft_b)):
                matrix.append(row + [1.0 if j == i else 0.0 for j in range(len(soft_ub))])
                rhs.append(value)
            result = linprog(objective, A_ub=np.array(matrix), b_ub=np.array(rhs),
                             bounds=bounds + [(0.0, None)] * len(soft_ub), method="highs",
                             options={"presolve": True})
            if result.success:
                relaxed = [{"constraint": soft_labels[i], "amount": float(result.x[n + i])}
                           for i in range(len(soft_ub)) if result.x[n + i] > 1e-7]
        if not result.success:
            conn.close()
            return {"status": "INFEASIBLE_PLAN", "foods": [], "slots": [], "nutrients": {},
                    "infeasible_constraints": labels + soft_labels, "needs_info": []}
    grams = [(candidates[i], float(result.x[i])) for i in range(n) if result.x[i] > 1e-7]
    slots = _templates(Path(template_path) if template_path else Path("data/templates/meal_templates.json"))
    plan_foods = [{"food_id": f["id"], "source_code": f["source_code"], "name": f["name"],
                   "grams": round(g, 6), "approximate": f["approximate"], "basis": "raw_edible_portion"} for f, g in grams]
    conn.close()
    slot_output = [{"slot": s["slot"], "foods": []} for s in slots]
    for index, food in enumerate(plan_foods):
        slot_output[index % len(slot_output)]["foods"].append(food)
    return {"status": "OK", "foods": plan_foods,
            "slots": slot_output,
            "nutrients": {}, "advisories": list(resolved.advisories),
            "added_salt_g_per_day": added_salt_g_per_day,
            "sodium_total_includes_added_salt_g": added_salt_g_per_day,
            "salt_assumption": "The plan assumes added salt is limited to this amount.",
            "price_objective": "reserved; no price term is used",
            "template_status": "DRAFT_HEURISTIC",
            "relaxed_soft_bounds": relaxed}
