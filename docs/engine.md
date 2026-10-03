# DietDB Engine

The planning pipeline loads declarative rules, validates the patient profile, resolves nutrient and exclusion constraints, solves a deterministic SciPy HiGHS linear program over raw edible portions, and independently recomputes totals from `food_nutrients` before accepting output.

Statuses are `OK`, `INCOMPLETE`, `CLINICIAN_REQUIRED`, `INFEASIBLE_RULES`, `INFEASIBLE_PLAN`, and `VERIFIER_REJECTED`. `INCOMPLETE` means required patient information is missing. Clinician-only conditions never produce an autoplan.

The meal template is explicitly `DRAFT_HEURISTIC`; it does not invent cooking yields. Added salt is a configurable reserve, defaulting to 5 g/day and using 393 mg sodium per gram. Prices are not an objective yet, but the optimizer output reserves that hook.

This engine deliberately contains no LLM, clinical rule authoring, cooking-yield assumptions, price data, allergen tagging, glycemic-index data, or purine data.
