# Planning engine

Pipeline (no language model): `Patient` validation -> `resolve` (rules to bounds) -> `optimize` (linear programming) -> `verify` (independent SQL recomputation) -> JSON.

Run: `python -m dietdb build --db /tmp/review.db && python -m dietdb load-rules --db /tmp/review.db --mode draft-review && python -m dietdb plan --db /tmp/review.db --patient examples/patient_t2dm.json --rules-mode draft-review --out plan.json`

Status codes: `OK`, `INCOMPLETE` (names the missing variables, or no rules loaded for the mode), `CLINICIAN_REQUIRED` (dialysis), `INFEASIBLE_RULES` (rules conflict), `INFEASIBLE_PLAN` (no plan fits; `diagnostics.would_need_to_relax` names the bounds), `NO_CANDIDATES`, `INVALID_INPUT`, `VERIFIER_REJECTED`.

Safety behaviour:
- HARD and SAFETY_CRITICAL bounds are constraints (with a 1% margin so whole-gram rounding cannot break them). SOFT bounds are constraints first and are relaxed with a heavy penalty only if the plan is otherwise impossible; every relaxation is reported.
- A food is excluded if any declared allergen is not tagged ABSENT (unknown is unsafe), if it does not fit the diet pattern, or if it lacks data for a nutrient that has an upper bound.
- Added salt is a planned quantity (1-5 g/day by default, `--salt-min/--salt-max`); sodium bounds include it (393.4 mg sodium per g salt). The plan assumes the patient keeps to that allowance.
- Weights are raw edible portion (IFCT basis). No cooking yields are applied.
- The verifier recomputes every total from the database and rejects the plan on any HARD violation, allergen, diet-pattern, per-food cap, slot range, energy-window or salt-range breach.
- Foods are limited to `data/curated/common_foods.json` (draft list) unless `--all-foods` is given. Meal structure comes from `data/templates/meal_templates.json` (draft heuristic, not clinical).
- Allergen tags are rule-based drafts from `src/dietdb/curated/allergens.py`; cross-reactivity and cross-contact are not modelled.

Not done: real (approved) clinical rules, prices, cooking yields, recipes/dishes, FODMAP, glycemic index, purines.
