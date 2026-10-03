# ENGINE TASKS v2 (replaces ENGINE_TASKS.md)

Repo reviewed at commit `fea3600` (G6 mostly done, E1 first version). Same working rules as before: ONE group per task, commit, paste real command output, stop. Never open `data/raw/*.csv`, `local/` or `*.db` in the editor. Never invent data. Ignore git history. Never write clinical numbers: the rule files in `data/rules/draft/` were drafted separately and stay `DRAFT` until a clinician approves them.

## State verified at fea3600
Done and good: deterministic builds (identical hash with a 3 s gap), seeds loaded by `build`, timestamps gone, 38 tests pass in 22 s with no stubs.
Still open from G6: only 2 data-quality flag types exist (still missing: energy-consistency check, hierarchy child-exceeds-parent check, the single `K.` prefix); `docs/schema.md` is still 23 lines.

## G6b: finish the leftovers (small)
1. Add the three missing data-quality checks (flag, never fix): CSV energy vs 4*protein + 9*fat + 4*available carbohydrate differing by more than 15%; hierarchy child greater than its parent; the `K.` language prefix.
2. Regenerate `docs/schema.md` from `PRAGMA table_info` plus one hand-written purpose line per table. Every table and column must be listed.
Acceptance: pytest green, hash test still passes.

## E1b: fix the constraint resolver (`src/dietdb/engine/constraints.py`)
The current `resolve()` has real bugs. I reproduced each with the drafted rules.
1. **No intersection of bounds.** It keeps only ONE rule per nutrient (the last one at the highest tier). For a CKD adult weighing 60 kg with 0.8 and 1.3 g/kg protein caps it returned 78 g instead of 48 g, silently dropping the stricter cap; for hypertension it dropped the 1,500 mg sodium target and kept 2,300. Required: group applicable rules per nutrient and per ENFORCEMENT CLASS (HARD, SOFT). Within a class and tier, intersect (highest min, lowest max). A THERAPEUTIC rule supersedes a BASELINE_DEFAULT rule on the same nutrient; SAFETY_CRITICAL always applies in addition. Keep the list of all contributing rule slugs.
2. **Conflict detection** must compare across rules: if the merged min exceeds the merged max within the HARD class, return `INFEASIBLE_RULES` naming every rule involved with its rationale and source. If a SOFT bound conflicts with a HARD bound, keep the HARD bound and mark the SOFT bound `OVERRIDDEN_BY_HARD`.
3. **`needs_info` must name the missing patient variables** (currently an empty list). Collect the variables referenced by the unevaluable part of `applies_when`. Treat a missing diagnosis flag as unknown (INCOMPLETE if any HARD or SAFETY_CRITICAL rule is undetermined). Do not default flags to false.
4. **`max_from_variable` / `min_from_variable`:** add these optional fields to the `Rule` model, the `rules` table and the loader. A rule with `max_from_variable` takes its bound from that patient variable (clinician-entered, canonical unit). If the rule applies but the variable is missing, add it to `needs_info` and set `INCOMPLETE`; it must never produce a plan with no bound. (Right now a CKD patient without a clinician potassium or phosphorus limit gets status OK and no potassium bound at all.)
5. **`PCT_OF_ENERGY`** is wrong: it multiplies by energy/100, which yields kcal. Convert to grams: protein and carbohydrate divide kcal by 4, fat by 9, per the nutrient's energy factor. Return `UNSUPPORTED_BASIS` for any other nutrient.
6. Bases: support PER_DAY, PER_KG_ACTUAL_WEIGHT, PER_1000_KCAL, PCT_OF_ENERGY. `PER_KG_IDEAL_WEIGHT`, `PER_MEAL` and `PER_WEEK` return `UNSUPPORTED_BASIS` in `needs_info` (never guess a formula).
7. `ADVISORY` rules and non-NUTRIENT rules (TAG, MEDICATION_CLASS, ADVISORY_TEXT) are collected into an `advisories` list (rule slug, rationale, source_locator) and never affect bounds.
8. Dialysis routing: if a rule whose slug starts with `ckd_dialysis` applies, set `planning_mode = CLINICIAN_ONLY_NO_AUTOPLAN` in the result and return status `CLINICIAN_REQUIRED`; no plan is computed.
9. Patient validation: do not crash on strings (`TypeError` on comparing a string to min/max); an unknown activity level must raise a clear error, not `KeyError`; allow the patient JSON to override the energy target (`energy_target_kcal`), documented.
10. Tests (use the FAKE fixture rules; plus a test that loads the real draft files with status flipped to APPROVED in a temp copy): the protein 48 g case; the hypertension sodium case (1,500 SOFT beside 2,300 HARD); the missing clinician potassium case returns INCOMPLETE and names `clinician_max_potassium_mg_day`; a min greater than max across two rules gives INFEASIBLE_RULES naming both; PCT_OF_ENERGY conversion with a hand-computed number; a dialysis patient returns CLINICIAN_REQUIRED.
Acceptance: all tests pass; the three patient cases in `tests/fixtures/` return exactly the numbers in the test expectations.

## G7: load the drafted rule package (do not change clinical content)
The package is in `docs/rule_package/` (copy it from the owner: `data/rules/draft/*.json`, `data/rules/draft_alternatives/`, `data/seed/patient_variables_conditions.json`, `data/conditions/draft_conditions.json`, `docs/rule_sources.md`). Place the files at the same relative paths in the repo.
1. The seed loader must also read `data/seed/patient_variables_conditions.json` (6 extra patient variables; `allowed_values` is stored as a JSON string).
2. Keep `load-rules` unchanged for production (it refuses DRAFT). Add `--mode draft-review` that loads `data/rules/draft/` including DRAFT rules into a separate database file only (never into `data/diet.db`), so the owner can try the engine on drafts. The mode name must appear in every output (`"RULES ARE UNREVIEWED DRAFTS"`).
3. Write a conditions loader (`conditions`, `condition_profiles`) for `draft_conditions.json`; validate `selector_expression` and `eligibility_expression` with the same expression validator; honour a profile's `planning_mode_override`.
4. Do not edit the numbers, rationale, sources or statuses in the rule files.
Acceptance: `load-rules --mode draft-review --db /tmp/review.db` loads 17 rules and 3 conditions; a test loads them and asserts those counts.

## E2: optimizer (`src/dietdb/engine/optimizer.py`)
Same as the earlier plan, with these changes.
1. `scipy.optimize.linprog` (HiGHS), pinned `scipy==` in requirements; foods sorted by id; deterministic solver options.
2. Candidate foods: exclude if an allergen for any declared patient allergy is PRESENT or UNKNOWN; if the diet pattern does not allow it; if a FOOD_EXCLUDE rule matches; or if it has NULL or NOT_ANALYSED for any nutrient that has a HARD or SAFETY_CRITICAL upper bound (unknown is unsafe). NOT_DETECTED counts as 0 and flags the food `approximate`.
3. HARD and SAFETY_CRITICAL bounds are hard constraints. SOFT bounds are also modelled as constraints first; if the plan is then infeasible, relax SOFT bounds through slack variables with a large per-unit penalty, and report every relaxed SOFT bound with the amount of violation. ADVISORY rules are only displayed.
4. **Added-salt reserve (safety-critical correctness issue).** IFCT sodium is the sodium naturally present in foods; most real sodium intake is added salt. A plan whose food sodium is under the cap says nothing about real intake. Add a plan parameter `added_salt_g_per_day` (default 5, a clearly labelled placeholder, configurable), convert at 393 mg sodium per g of salt, and subtract it from every sodium bound before solving. The output must state `sodium_total_includes_added_salt_g: <value>` and that the plan assumes the salt is actually limited to that amount.
5. Structure from `data/templates/meal_templates.json` (slots and allowed food groups with generous gram ranges), marked `"status": "DRAFT_HEURISTIC"`, listed in `docs/open_questions.md` for the owner. Objective: minimise energy deviation, then spread across foods, then total grams. No price term yet (document the hook).
6. Weights are raw edible portion weights (`basis: raw_edible_portion`). No cooking yields invented.
7. Infeasible plan: solve a second LP relaxing HARD bounds with minimal total relative violation, and report which bounds would have to give; never output a plan that violates a HARD bound.
8. Output JSON per slot with grams, food id and source code; per-nutrient totals vs bounds; contributing rule slugs; approximate flags; advisories; salt reserve.
9. Tests (fake fixtures): feasible; infeasible with diagnosis; allergen UNKNOWN excluded; identical input gives byte-identical output; the salt reserve reduces the food sodium bound by the right amount.

## E3: independent verifier (`src/dietdb/engine/verifier.py`)
Recompute every nutrient total from grams via SQL on `food_nutrients` (not from the optimizer's matrices) and check all HARD/SAFETY bounds, allergens, diet rules, per-food caps, the energy window, and the added-salt reserve. The pipeline refuses to output a plan that fails. Mutation tests: add 500 g of a high-potassium food; add an allergen food; change grams; remove the salt reserve; each must be caught.

## E4: command line and report
1. `python -m dietdb plan --db <db> --patient patient.json [--rules-mode test|draft-review|production] --out plan.json` runs resolve, optimize, verify, and writes status (`OK`, `INCOMPLETE`, `CLINICIAN_REQUIRED`, `INFEASIBLE_RULES`, `INFEASIBLE_PLAN`, `VERIFIER_REJECTED`), the plan, `needs_info`, advisories and each applied rule's rationale and source verbatim (no generated explanations).
2. Patient fixtures under `tests/fixtures/`: T2D + hypertension; CKD G3b + T2D with clinician limits; CKD without clinician limits (must be INCOMPLETE); dialysis (CLINICIAN_REQUIRED); allergic; conflicting rules. Golden-output tests.
3. `docs/engine.md`: pipeline, status codes, what is deliberately not done (no LLM, no clinical content, no cooking yields, no prices).
4. Final report with real output of: full pytest; two fresh builds with hashes; `plan` on each fixture; the verifier mutation tests. Stop.
