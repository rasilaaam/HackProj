"""Independent plan verifier.

It does NOT use the optimizer's matrices or candidate loader. It recomputes every total from the plan's
grams with its own SQL on food_nutrients, then checks every HARD bound, the energy window, allergens, the
diet pattern, per-food caps, the meal template and the salt allowance. SOFT bounds are reported, not failed.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from dietdb.engine.optimizer import DIET_TAG, REPORT_NUTRIENTS, SALT_SODIUM_MG_PER_G, bounds_of

EPS = 1e-9


def verify(db: str, plan: dict[str, Any], resolved_nutrients: dict[str, Any], energy_kcal: float, template: dict[str, Any],
           allergens: list[str], pattern: str, salt_min_g: float, salt_max_g: float) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    bounds = bounds_of(resolved_nutrients)
    needed = sorted(set(REPORT_NUTRIENTS) | set(bounds))
    items = plan["items"]
    salt_g = float(plan["salt_g"])
    violations: list[dict[str, Any]] = []
    totals = {n: 0.0 for n in needed}
    per_slot_energy: dict[str, float] = {}
    round_tol: dict[str, float] = {}   # grams are whole numbers: allow +/-0.5 g of each food in energy checks
    group_slot: dict[tuple[str, str], float] = {}
    per_food: dict[int, float] = {}
    marks = ",".join("?" for _ in needed)
    for it in items:
        fid, grams = it["food_id"], float(it["grams"])
        row = conn.execute("SELECT f.english_name, g.code FROM foods f JOIN food_groups g ON g.id = f.food_group_id WHERE f.id = ?", (fid,)).fetchone()
        if row is None:
            violations.append({"check": "FOOD_EXISTS", "food_id": fid}); continue
        if row[1] != it["group"]: violations.append({"check": "GROUP_MISMATCH", "food_id": fid})
        vals = {n: (v, s) for n, v, s in conn.execute(
            f"SELECT n.canonical_name, fn.value_canonical, fn.value_status FROM food_nutrients fn JOIN nutrients n ON n.id = fn.nutrient_id "
            f"WHERE fn.food_id = ? AND n.canonical_name IN ({marks})", [fid, *needed])}
        for n in needed:
            v, status = vals.get(n, (None, "NOT_ANALYSED"))
            if v is None:
                has_max = bounds.get(n, {}).get("hard", {}).get("max") is not None or bounds.get(n, {}).get("soft", {}).get("max") is not None
                if n == "energy_kcal" or (status != "NOT_DETECTED" and has_max):
                    violations.append({"check": "UNKNOWN_NUTRIENT_IN_BOUNDED_FOOD", "food_id": fid, "nutrient": n})
                v = 0.0
            totals[n] += grams / 100.0 * float(v)
        e100 = float(vals.get("energy_kcal", (0.0, ""))[0] or 0.0)
        per_slot_energy[it["slot"]] = per_slot_energy.get(it["slot"], 0.0) + grams / 100.0 * e100
        round_tol[it["slot"]] = round_tol.get(it["slot"], 0.0) + 0.005 * e100
        group_slot[(it["slot"], it["group"])] = group_slot.get((it["slot"], it["group"]), 0.0) + grams
        per_food[fid] = per_food.get(fid, 0.0) + grams
        if allergens:
            marks_a = ",".join("?" for _ in allergens)
            seen = {c: p for c, p in conn.execute(
                f"SELECT a.code, fa.presence FROM food_allergens fa JOIN allergens a ON a.id = fa.allergen_id WHERE fa.food_id = ? AND a.code IN ({marks_a})", [fid, *allergens])}
            for a in allergens:
                if seen.get(a, "UNKNOWN") != "ABSENT":
                    violations.append({"check": "ALLERGEN", "food_id": fid, "allergen": a, "presence": seen.get(a, "UNKNOWN")})
        wanted = DIET_TAG.get(pattern)
        if pattern == "vegan" and it["group"] == "L": violations.append({"check": "DIET_PATTERN", "food_id": fid})
        if wanted is not None:
            ok = conn.execute("SELECT 1 FROM diet_type_tags t JOIN diet_types d ON d.id = t.diet_type_id WHERE t.food_id = ? AND d.code = ? AND t.is_compatible = 1", (fid, wanted)).fetchone()
            if not ok: violations.append({"check": "DIET_PATTERN", "food_id": fid})
    totals["sodium"] += salt_g * SALT_SODIUM_MG_PER_G
    if not (salt_min_g - EPS <= salt_g <= salt_max_g + EPS):
        violations.append({"check": "SALT_RANGE", "salt_g": salt_g})
    table: dict[str, Any] = {}
    soft_violations: list[dict[str, Any]] = []
    for n in sorted(bounds):
        total = totals.get(n, 0.0)
        row = {"total": round(total, 3)}
        for cls in ("hard", "soft"):
            b = bounds[n][cls]
            row[cls] = {"min": b.get("min"), "max": b.get("max")}
            if b.get("max") is not None and total > b["max"] + 1e-6:
                (violations if cls == "hard" else soft_violations).append({"check": f"{cls.upper()}_MAX", "nutrient": n, "total": round(total, 3), "limit": b["max"]})
            if b.get("min") is not None and total < b["min"] - 1e-6:
                (violations if cls == "hard" else soft_violations).append({"check": f"{cls.upper()}_MIN", "nutrient": n, "total": round(total, 3), "limit": b["min"]})
        table[n] = row
    tol = float(template.get("energy_tolerance", 0.10))
    all_tol = sum(round_tol.values()) + 1e-6
    if not (energy_kcal * (1 - tol) - all_tol <= totals["energy_kcal"] <= energy_kcal * (1 + tol) + all_tol):
        violations.append({"check": "ENERGY_WINDOW", "total": round(totals["energy_kcal"], 1), "target": round(energy_kcal, 1)})
    caps = template.get("per_food_max_g_by_group", {}); default_cap = float(template.get("per_food_max_g_default", 200))
    group_of = {it["food_id"]: it["group"] for it in items}
    for fid, grams in per_food.items():
        cap = float(caps.get(group_of[fid], default_cap))
        if grams > cap + 0.5 * len([i for i in items if i["food_id"] == fid]):
            violations.append({"check": "PER_FOOD_CAP", "food_id": fid, "grams": grams, "cap": cap})
    for slot, spec in template["slots"].items():
        lo, hi = spec["energy_share"]
        e = per_slot_energy.get(slot, 0.0)
        slot_tol = round_tol.get(slot, 0.0) + 1e-6
        if e > hi * energy_kcal + slot_tol or e < lo * energy_kcal - slot_tol:
            violations.append({"check": "SLOT_ENERGY_SHARE", "slot": slot, "kcal": round(e, 1)})
    for (slot, g), grams in sorted(group_slot.items()):
        rng = template["slots"].get(slot, {}).get("groups", {}).get(g)
        n_items = len([i for i in items if i["slot"] == slot and i["group"] == g])
        if rng is None or grams > rng[1] + 0.5 * n_items:
            violations.append({"check": "SLOT_GROUP_RANGE", "slot": slot, "group": g, "grams": grams})
    conn.close()
    return {"ok": not violations, "violations": violations, "soft_violations": soft_violations,
            "totals": {k: round(v, 3) for k, v in sorted(totals.items())}, "bounds": table,
            "per_slot_energy_kcal": {k: round(v, 1) for k, v in sorted(per_slot_energy.items())}}
