"""Independent SQL-backed verification of optimizer output."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from dietdb.engine.optimizer import SALT_SODIUM_MG_PER_G
from dietdb.engine.db import connect_readonly


def verify(plan: dict[str, Any], db: str | Path, resolved: Any,
           patient: dict[str, Any] | None = None) -> dict[str, Any]:
    conn = connect_readonly(db)
    totals: dict[str, float] = {}
    errors: list[str] = []
    for food in plan.get("foods", []):
        grams = float(food.get("grams", 0))
        if grams < 0:
            errors.append(f"negative grams for food {food.get('food_id')}")
            continue
        allergy_codes = patient.get("allergy_list", []) if patient else []
        if isinstance(allergy_codes, str): allergy_codes = [x.strip() for x in allergy_codes.split(",") if x.strip()]
        if allergy_codes:
            marks = ",".join("?" * len(allergy_codes))
            bad = conn.execute(f"""SELECT 1 FROM food_allergens fa JOIN allergens a ON a.id=fa.allergen_id
                WHERE fa.food_id=? AND a.code IN ({marks}) AND fa.presence IN ('PRESENT','UNKNOWN')""",
                [food["food_id"], *allergy_codes]).fetchone()
            if bad: errors.append(f"allergen-excluded food {food['food_id']}")
        rows = conn.execute("""SELECT n.canonical_name, fn.value_canonical, fn.value_status
            FROM food_nutrients fn JOIN nutrients n ON n.id=fn.nutrient_id WHERE fn.food_id=?""", (food["food_id"],))
        for name, value, status in rows:
            if value is not None and status != "NOT_ANALYSED":
                totals[name] = totals.get(name, 0.0) + float(value) * grams / 100.0
    salt = float(plan.get("added_salt_g_per_day", 5.0))
    for nutrient, bound in resolved.nutrients.items():
        value = totals.get(nutrient, 0.0)
        maximum = bound.get("max")
        minimum = bound.get("min")
        if nutrient == "sodium" and maximum is not None:
            maximum -= SALT_SODIUM_MG_PER_G * salt
        if maximum is not None and value > maximum + 1e-6:
            errors.append(f"{nutrient} exceeds maximum: {value} > {maximum}")
        if minimum is not None and value + 1e-6 < minimum:
            errors.append(f"{nutrient} below minimum: {value} < {minimum}")
    energy = totals.get("energy_kcal")
    target = getattr(resolved, "energy_target_kcal", None)
    if target is not None:
        if energy is None:
            errors.append("energy target cannot be verified: no energy data")
        elif not target * 0.8 - 1e-5 <= energy <= target * 1.2 + 1e-5:
            errors.append(f"energy outside target window: {energy} not in [{target * 0.8}, {target * 1.2}]")
    conn.close()
    return {"ok": not errors, "errors": errors, "totals": totals,
            "sodium_total_includes_added_salt_g": salt}
