# ENGINE TASKS: fixes (G6), then the deterministic planning engine (E1-E4)

Repo reviewed at commit `a0d14a8`. Read `docs/AGENT_HANDOFF.md` sections 1, 2 (rules) once and `docs/schema.md`. Same working rules as `docs/FINAL_TASKS.md`: ONE group per task, commit, paste real output, stop. Never open `data/raw/*.csv`, `local/` or `*.db` in the editor. Never invent data. Ignore git history.

## What the engine is for
Given a patient (JSON of values for `patient_variables`) and the database, produce a one-day meal plan whose nutrient totals satisfy every applicable rule, with NO language model involved. A later layer will let an LLM extract the patient JSON and explain results; it will never compute numbers. The engine must be fully deterministic and every output number must be traceable to a database row.

## G6: repair regressions (do this first)
1. **Determinism is broken.** `data_quality_flags.flagged_at` (default `datetime('now')`) is inside the hash, so two fresh builds a few seconds apart differ (I measured `9f5ba4e1…` vs `1e0716b6…`). Remove the timestamp column (and `flagged_by` default noise) from content tables. Make `get_db_hash` skip `build_metadata`, virtual FTS tables and FTS shadow tables, sort by explicit primary key, and not store its own hash inside the hashed data.
2. **Add the missing test:** build twice with `time.sleep(2)` between and assert identical hashes; also assert ids are stable (`foods.id` range 1..542, A015 has the same id both times). There is currently no hash test at all.
3. **`python -m dietdb build` must also seed** `allergens`, `patient_variables` and `diet_types` (from `data/seed/`). Right now they are empty until `load-rules` runs. `load-rules` must stay idempotent.
4. **Missing data-quality checks** from G4: energy consistency (CSV energy vs 4*protein + 9*fat + 4*available carbohydrate differing by more than 15%: flag, don't fix), hierarchy children exceeding their parent, the single `K.` language prefix. Currently only two flag types exist.
5. **Docs:** `docs/schema.md` is 23 lines. It must list every table and column and why it exists (generate it from `PRAGMA table_info` plus hand-written purpose lines); delete the 1-line `SCHEMA.md`. In README, only claim "deterministic" after item 2 passes; use real test counts.
6. Replace Pydantic class-based `Config` in `models_rules.py` with `ConfigDict` (silences the warning).
Acceptance: full pytest green; the two-build hash test passes with a 2 s gap.

## E1: patient + constraint resolution (`src/dietdb/engine/constraints.py`)
Pure functions, no solver yet.
1. `Patient`: Pydantic model validated against `patient_variables` (unknown variable rejected; value outside its plausibility range rejected).
2. `resolve(patient, db, mode)` returns a `ResolvedConstraints` object:
   - applicable rules: evaluate each rule's `applies_when` tree over the patient. If a referenced variable is missing, the rule is `UNDETERMINED`: add it to `needs_info` (variable name, which rules need it) and, for HARD/SAFETY_CRITICAL rules, mark the whole result `INCOMPLETE`. Never silently skip such a rule.
   - tiers: a THERAPEUTIC rule on a nutrient supersedes the BASELINE_DEFAULT rule on the same nutrient; SAFETY_CRITICAL always wins.
   - convert every bound to an absolute per-day number in the nutrient's canonical unit. Supported bases: PER_DAY, PER_MEAL (kept per meal), PER_KG_ACTUAL_WEIGHT (needs weight), PER_1000_KCAL and PCT_OF_ENERGY (need the energy target; 1 g protein/carbohydrate = 4 kcal, 1 g fat = 9 kcal). PER_KG_IDEAL_WEIGHT and anything else: return `needs_info` / `UNSUPPORTED_BASIS`, never invent a formula.
   - energy target: Mifflin-St Jeor resting energy x activity factor (1.2, 1.375, 1.55, 1.725, 1.9 for sedentary, light, moderate, active, very active). Document these as standard formulas, not clinical advice; allow a rule or the patient to override the target.
   - merge: for each nutrient take the highest min and lowest max; allergen exclusions and food exclusions union.
   - if any nutrient has min > max, return status `INFEASIBLE_RULES` listing the two (or more) rules in conflict with their rationale text and sources. Never relax a bound silently.
3. Tests with the FAKE fixture rules only: tier supersession; union of allergens; conflicting min/max gives INFEASIBLE_RULES naming both rules; missing lab gives needs_info and INCOMPLETE; unsupported basis handled; every conversion basis tested with hand-computed numbers.

## E2: optimizer (`src/dietdb/engine/optimizer.py`)
1. Add `scipy` pinned with `==` and use `scipy.optimize.linprog` (HiGHS). Deterministic: fixed ordering of foods (by food id) and fixed solver options.
2. Candidate foods: exclude a food if (a) its allergen status for any patient allergen is PRESENT or UNKNOWN, (b) it violates the patient's diet pattern tag, (c) a FOOD_EXCLUDE rule matches it, (d) it has NOT_ANALYSED/NULL for any nutrient that has a HARD or SAFETY_CRITICAL upper bound (unknown is unsafe). NOT_DETECTED counts as 0 in sums and sets a per-food `approximate` flag reported in the output.
3. Structure comes from `data/templates/meal_templates.json` (slots: breakfast, lunch, dinner, snack; for each slot the allowed food groups with generous min/max grams). These are product-design placeholders, not clinical values: mark the file `"status": "DRAFT_HEURISTIC"`, use wide ranges, and list them in `docs/open_questions.md` for the owner's review. Global caps: max grams per food per day.
4. Variables: raw grams of each candidate food per slot. Constraints: every resolved nutrient bound (per day and per meal where applicable), the energy window, group ranges. Objective: minimize energy deviation first (slack variables), then spread across foods (cap per food), then total grams. Prices are not loaded, so no cost term yet; leave a documented hook.
5. If infeasible, solve a second LP that adds slack variables to every HARD bound with minimal total relative violation, and report exactly which constraints would have to give. The result is `INFEASIBLE_PLAN` with that diagnosis. Never output a plan that violates a HARD bound.
6. Weights are RAW weights (IFCT is mostly raw). Say so in the output (`basis: raw_edible_portion`). Do not invent cooking yields.
7. Output JSON: per slot, foods with grams and the food id and source code; per-nutrient totals vs bounds; list of rule ids that shaped the plan; approximate flags.
8. Tests (fake fixtures): a feasible case; an infeasible case with the diagnosis naming constraints; allergen UNKNOWN food excluded; same input run twice gives byte-identical output.

## E3: independent verifier (`src/dietdb/engine/verifier.py`)
Re-verify any plan WITHOUT the optimizer's matrices: read food_nutrients from the database via SQL, recompute every nutrient total from grams, and check every HARD/SAFETY bound, allergen and diet rule, per-food caps and the energy window. Return a list of violations with rule ids. The pipeline must call it on every plan and refuse to output a plan that fails. Tests: mutation tests that tamper with a valid plan (add 500 g of a high-potassium food; add an allergen food; change grams) and assert the verifier catches each.

## E4: command line and report
1. `python -m dietdb plan --db data/diet.db --patient patient.json --rules-mode test --out plan.json` runs resolve, optimize, verify, and writes: status (`OK`, `INCOMPLETE`, `INFEASIBLE_RULES`, `INFEASIBLE_PLAN`, `VERIFIER_REJECTED`), the plan, needs_info, and the rationale/source text of each applied rule (from the rules table, verbatim; no generated explanations).
2. Add 4 fake patient fixtures under `tests/fixtures/` (feasible; conflicting rules; missing lab; allergic) and golden-output tests.
3. `docs/engine.md`: the pipeline, the status codes, what is deliberately not done (no LLM, no clinical rule content, no cooking yields, no prices), and how to run it.
4. Final report with real output of: full pytest; two fresh builds with hashes; `plan` on each fixture patient; the verifier mutation tests. Stop. Do NOT write real disease rules or clinical numbers; the owner will supply reviewed rule files (`data/rules/*.json`, status APPROVED) separately.
