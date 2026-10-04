"""Pipeline: validate patient -> resolve rules -> optimize -> independently verify -> JSON-able result."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from dietdb.engine.constraints import Patient, resolve
from dietdb.engine.optimizer import DIET_TAG, SALT_SODIUM_MG_PER_G, allergen_codes, load_template, optimize
from dietdb.engine.verifier import verify

DEFAULT_TEMPLATE = Path(__file__).resolve().parents[3] / "data/templates/meal_templates.json"
COMMON_FOODS = Path(__file__).resolve().parents[3] / "data/curated/common_foods.json"
BANNERS = {"draft-review": "RULES ARE UNREVIEWED DRAFTS: not clinical advice",
           "test": "TEST FIXTURE RULES: not medical",
           "production": "Rules reviewed and approved; this is not medical advice"}


def _references_variable(expression: Any, variable: str) -> bool:
    if not isinstance(expression, dict):
        return False
    if expression.get("var") == variable:
        return expression.get("op") == "==" and expression.get("value") is True
    if "not" in expression:
        return _references_variable(expression["not"], variable)
    return any(_references_variable(child, variable) for key in ("and", "or") for child in expression.get(key, []))


def _rule_info(db: str, slugs: list[str]) -> list[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    out = []
    for slug in sorted(set(slugs)):
        r = conn.execute("SELECT slug, name, enforcement, tier, status, rationale, source_locator, evidence_grade, reviewed_by, reviewed_at FROM rules WHERE slug = ?", (slug,)).fetchone()
        if r: out.append(dict(zip(("slug", "name", "enforcement", "tier", "status", "rationale", "source_locator", "evidence_grade", "reviewed_by", "reviewed_at"), r)))
    conn.close()
    return out


PATTERN_ALIASES = {"VEGETARIAN": "VEGETARIAN", "VEG": "VEGETARIAN", "VEGAN": "VEGAN", "EGGETARIAN": "EGGETARIAN",
                   "FISHETARIAN": "FISHETARIAN", "NONVEG": "NONVEG", "NON-VEG": "NONVEG", "NON_VEGETARIAN": "NONVEG",
                   "NON-VEGETARIAN": "NONVEG", "NON VEGETARIAN": "NONVEG"}
PATTERN_KEYS = {"VEGETARIAN": "vegetarian", "VEGAN": "vegan", "EGGETARIAN": "eggetarian", "FISHETARIAN": "fishetarian", "NONVEG": "non_vegetarian"}


def make_plan(db: str, values: dict[str, Any], rules_mode: str = "production", template_path: str | Path | None = None,
              salt_min_g: float = 1.0, salt_max_g: float = 5.0, common_foods_only: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "OK", "rules_mode": rules_mode, "banner": BANNERS.get(rules_mode),
                              "assumptions": ["Weights are raw edible portion (IFCT basis)",
                                              "Added salt is planned: sodium includes salt_g x 393.4 mg",
                                              "Allergen tags are rule-based drafts" ]}
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    bh = conn.execute("SELECT value FROM build_metadata WHERE key = 'build_hash'").fetchone()
    conn.close()
    result["database_hash"] = bh[0] if bh else None
    values = dict(values)
    if "dietary_pattern" in values:
        canon = PATTERN_ALIASES.get(str(values["dietary_pattern"]).strip().upper())
        if canon is None:
            return {**result, "status": "INVALID_INPUT", "message": f"unsupported dietary_pattern '{values['dietary_pattern']}'; supported: {sorted(PATTERN_KEYS)}"}
        values["dietary_pattern"] = canon
    try:
        patient = Patient.from_database(values, db)
    except ValueError as exc:
        return {**result, "status": "INVALID_INPUT", "message": str(exc)}
    if "allergy_list" not in values:
        return {**result, "status": "INCOMPLETE", "needs_info": [{"rule": None, "variables": ["allergy_list"], "reason": "required by the planner; use [] if none"}]}
    if "dietary_pattern" not in values:
        result["assumptions"].append("dietary_pattern not given: no vegetarian/egg/fish filter applied")
    pattern = PATTERN_KEYS[values.get("dietary_pattern", "NONVEG")]
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    n_rules = conn.execute("SELECT count(*) FROM rules WHERE status = 'APPROVED' OR (? IN ('test','draft-review') AND status IN ('TEST_FIXTURE','DRAFT'))", (rules_mode,)).fetchone()[0]
    conn.close()
    if n_rules == 0:
        return {**result, "status": "INCOMPLETE", "message": f"no rules are loaded for mode '{rules_mode}'; run load-rules first"}
    if rules_mode == "production":
        active_conditions = sorted(name for name, value in values.items() if name.startswith("dx_") and value is True)
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as guard_conn:
            approved = [json.loads(row[0]) for row in guard_conn.execute("SELECT applies_when FROM rules WHERE status = 'APPROVED'")]
        missing_conditions = [name for name in active_conditions
                              if not any(_references_variable(expression, name) for expression in approved)]
        if missing_conditions:
            return {**result, "status": "NO_APPROVED_RULES", "conditions": missing_conditions,
                    "message": "No APPROVED rules cover active condition(s): " + ", ".join(missing_conditions)}
    try:
        allergens = allergen_codes(values["allergy_list"])
        resolved = resolve(patient, db, rules_mode)
    except ValueError as exc:
        return {**result, "status": "INVALID_INPUT", "message": str(exc)}
    result.update({"needs_info": resolved.needs_info, "advisories": resolved.advisories, "conflicts": resolved.conflicts,
                   "energy_target_kcal": None if resolved.energy_target_kcal is None else round(resolved.energy_target_kcal, 1),
                   "planning_mode": resolved.planning_mode})
    if resolved.status != "OK":
        return {**result, "status": resolved.status}
    if resolved.energy_target_kcal is None:
        return {**result, "status": "INCOMPLETE", "needs_info": [{"rule": None, "variables": ["sex", "age_years", "weight_kg", "height_cm", "activity_level"], "reason": "energy target"}]}
    template = load_template(template_path or DEFAULT_TEMPLATE)
    allowed = None
    if common_foods_only and COMMON_FOODS.exists():
        allowed = {f["source_code"] for f in json.loads(COMMON_FOODS.read_text())["foods"]}
        result["assumptions"].append("Foods limited to the draft common-foods list (data/curated/common_foods.json)")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        plan = optimize(conn, resolved.nutrients, resolved.energy_target_kcal, template, allergens, pattern, salt_min_g, salt_max_g, allowed)
    finally:
        conn.close()
    result["diagnostics"] = plan.diagnostics
    slugs = [r for e in resolved.nutrients.values() for r in e.get("rules", [])]
    for e in resolved.nutrients.values():
        for cls in ("hard", "soft"):
            slugs += (e.get(cls) or {}).get("rules", [])
    slugs += [a["rule"] for a in resolved.advisories if "rule" in a]
    result["rules_applied"] = _rule_info(db, slugs)
    if plan.status != "OK":
        return {**result, "status": "INFEASIBLE_PLAN" if plan.status == "INFEASIBLE_PLAN" else "NO_CANDIDATES"}
    body = {"items": plan.items, "salt_g": plan.salt_g}
    check = verify(db, body, resolved.nutrients, resolved.energy_target_kcal, template, allergens, pattern, salt_min_g, salt_max_g)
    result["verification"] = check
    if not check["ok"]:
        return {**result, "status": "VERIFIER_REJECTED"}
    by_slot: dict[str, list[dict[str, Any]]] = {}
    for it in plan.items: by_slot.setdefault(it["slot"], []).append({k: v for k, v in it.items() if k != "slot"})
    result["plan"] = {"slots": by_slot, "added_salt_allowance_g": plan.salt_g,
                      "sodium_total_includes_added_salt_mg": round(plan.salt_g * SALT_SODIUM_MG_PER_G, 1)}
    return result


def dumps(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, default=list) + "\n"
