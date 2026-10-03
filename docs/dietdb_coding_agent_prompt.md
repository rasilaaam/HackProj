# CODING AGENT PROMPT — Finish DietDB (HackProj) into a working user product

## 0. Context you must internalize first

Repo: https://github.com/rasilaaam/HackProj (a Python project, package `dietdb` under `src/`).

This is a **diet-plan suggestion engine for patients in India with diet-restricting diseases** (Type 2 diabetes, CKD, hypertension, food allergies). The architecture has one non-negotiable invariant:

> **No nutrient number and no safety decision may ever be produced by the UI, an LLM, or any non-deterministic code. Every number comes from the SQLite database (built from IFCT 2017 food composition data) and the deterministic engine (`src/dietdb/engine/`).**

Pipeline that already exists (verify it runs, then improve — do not redesign):

1. `python -m dietdb build --db data/diet.db` — applies `migrations/*.sql`, verifies the IFCT CSV sha256, loads 542 foods / 166 nutrients / ~90k measurements via `ingest/ifct_loader.py`, seeds `allergens` + `patient_variables` from `data/seed/`, writes `build_metadata` with a deterministic content hash.
2. `python -m dietdb load-rules --db <db> --mode production|test|draft-review` — validates declarative JSON rules (`models_rules.py`, `rules.py`) and inserts them into the `rules` table. `draft-review` additionally loads `data/conditions/draft_conditions.json` and **requires the DB path to NOT be `data/diet.db`** (use a copy).
3. `python -m dietdb plan --db <db> --patient <json> --rules-mode <mode> --out <json>` — full pipeline: `engine/constraints.py` (validates patient against `patient_variables`, evaluates rule `applies_when` expressions, merges bounds, detects conflicts) → `engine/optimizer.py` (SciPy HiGHS LP over raw edible portions) → `engine/verifier.py` (independent SQL recomputation of totals vs bounds) → writes a JSON plan.

Statuses: `OK`, `INCOMPLETE` (missing patient info), `CLINICIAN_REQUIRED` (dialysis etc., never autoplan), `INFEASIBLE_RULES`, `INFEASIBLE_PLAN`, `VERIFIER_REJECTED`.

**The README is stale — trust code, not docs. `docs/AGENT_HANDOFF.md` is from an earlier phase and mostly describes completed work; its remaining "later stages" (allergen tagging of foods, GI/purine data, LLM layer, web interface) are context, not your job, EXCEPT where this prompt explicitly asks for them.**

## 1. Global rules (violating any of these = failed task)

1. **Never invent clinical data.** No nutrient values, thresholds, citations, or guideline numbers from memory. Rules in `data/rules/draft/` have `status: DRAFT` with explicitly unverified sources — **keep them DRAFT**. Do NOT flip anything to `APPROVED` to make tests pass. The product must work and be clearly labeled as using unreviewed draft rules.
2. **Missing is not zero.** Never convert blank/trace/not-analysed into 0. Preserve `value_status` semantics (`MEASURED`, `TRACE`, `NOT_DETECTED`, `NOT_ANALYSED`, `CALCULATED`) end-to-end.
3. **Determinism.** Same inputs → same DB hash and same plan. Do not break `get_db_hash` in `src/dietdb/__main__.py`. Two fresh builds must produce identical hashes.
4. **Provenance.** Every new data row carries source info. Never commit IFCT book text; `local/` must stay untracked (`git ls-files local | wc -l` must print 0).
5. **Read-only at runtime.** Engine/repository reads open the DB with `mode=ro`; `PRAGMA foreign_keys = ON` on every connection.
6. **No `eval`/`exec`.** Rule conditions stay declarative data.
7. **Don't rewrite git history or force-push.** Commit in small logical chunks with clear messages.
8. **Trust only what you can run.** The final report must paste real command output, not claims.

## 2. Phase 0 — Baseline recon (run first, fix nothing yet)

```bash
git clone https://github.com/rasilaaam/HackProj.git && cd HackProj
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
python -m dietdb build --db data/diet.db --output-hash   # run twice; hashes must match
pytest -q                                                # record pass/fail counts
cp data/diet.db /tmp/draft.db
python -m dietdb load-rules --db /tmp/draft.db --mode draft-review
printf '{"age_years":45,"sex":"M","weight_kg":70,"height_cm":172,"activity_level":"moderate","dx_type2_diabetes":true,"energy_target_kcal":2200}' > /tmp/patient.json
python -m dietdb plan --db /tmp/draft.db --patient /tmp/patient.json --rules-mode draft-review --out /tmp/plan.json
cat /tmp/plan.json
```

Record everything that fails or looks wrong. Then work through Phase 1–5. If a Phase 1 item turns out to be already fixed, verify with a test and move on — say so in the report.

## 3. Phase 1 — Bug fixes (each item: write/adjust a failing test first, then fix)

1. **Stale test fixtures (`tests/conftest.py`).**
   - `sample_patient_variables` uses variables that don't exist in seeds: `has_t2dm` → `dx_type2_diabetes`, `egfr` → `egfr_ml_min_1_73m2`, `hba1c_percent` → `hba1c_pct`. Fix to match `data/seed/patient_variables.json` + `patient_variables_conditions.json`.
   - `sample_rule.applies_when` is `{"op": "eq", "field": ...}` — the real schema is `{"var", "op", "value"}` with `op ∈ {<, <=, >, >=, ==, !=, in}` (see `rules.py: OPS`). Fix it; a rule with `"eq"` must fail validation.
   - The session-scoped `ifct_db` fixture applies only migrations 001 and 002. It must apply **all** files in `migrations/` in sorted order (or reuse the same build function as `__main__.build_database` against a temp path) so engine tests have the `rules`/`conditions` tables.
   - Add a session fixture that builds a draft DB copy and loads `data/rules/draft/*.json` + conditions in `draft-review` semantics, for end-to-end engine tests.
2. **`dietary_pattern` case-sensitivity bug (`engine/optimizer.py:_foods`).** The loader uppercases CSV diet tags into `diet_types.code` (e.g. `VEGETARIAN`), but the patient enters `"vegetarian"`, so `d.code = ?` matches nothing and **every food gets excluded** → bogus `INFEASIBLE_PLAN`. Fix: normalize both sides (uppercase; map common synonyms like `veg`/`non-veg`/`nonveg`). Also make `sex`, `activity_level`, `dietary_pattern`, `renal_replacement` proper ENUMs: fill `patient_variables.allowed_values` (JSON list in the DB column) from the seed data / code constants, and enforce in `Patient.from_database` (which currently only enforces ENUM when `allowed` is non-empty). Tests: a vegetarian patient gets a feasible plan with zero meat-group foods; `"Vegetarian"` and `"vegetarian"` both work.
3. **Allergen safety gap (critical).** `food_allergens` is never populated, so the allergy exclusion in `optimizer._foods` and `verifier.verify` silently does nothing. Fix BOTH:
   - (a) Populate `food_allergens` deterministically at build/seed time from food-group inference: group L (Milk & Milk Products) → `MILK`; group M (Egg) → `EGG`; groups P/Q/R/S (fish/shellfish/mollusks) → `FISH`, `CRUSTACEAN`, `MOLLUSC` as appropriate; nut/seeds items in group H → `TREE_NUTS` / `PEANUTS` only when the food name matches a configured list in a new data file `data/seed/food_allergen_inferences.json` (food source_code → allergen codes, so humans can review/edit it; start it from group-level defaults and leave it clearly labeled `INFERRED_FROM_GROUP`). Use `presence = 'PRESENT'` for inferences and record the inference in `data_quality_flags` or a provenance column. Use the allergen codes that exist in `data/seed/allergens.json`; add missing ones there with the EU-1169/2011 citation if needed.
   - (b) Defense in depth: if a patient supplies `allergy_list` and NO `food_allergens` rows exist for those allergens, the engine must return `needs_info`/a prominent warning — never silently proceed. Test: patient allergic to `MILK` gets a plan containing zero group-L foods, and the verifier agrees.
4. **Optimizer realism (`engine/optimizer.py`).**
   - Per-food bounds are `(0, 10000)` grams — a plan can serve 9 kg of one food. Add `max_food_grams_per_day: float = 500.0` parameter to `optimize()`; LP bounds become `(0, max_food_grams_per_day)`. Add CLI flag `--max-food-grams-per-day`. Keep it deterministic.
   - Degenerate epsilon servings: after the solve, drop foods with `grams < 5` and re-run `verifier.verify`; if verification then fails bounds, return `VERIFIER_REJECTED` with the reason (do not silently trim). Put the trim + reverify logic in the `plan` CLI (or a small wrapper), not inside `optimize`, so `optimize` stays a pure LP.
   - Energy row: foods missing `energy_kcal` data contribute 0 energy silently. Exclude candidates with no energy data when an energy target is active and add an advisory listing how many foods were skipped for missing hard-nutrient data.
5. **Meal slot assignment is a round-robin that ignores the template.** `_templates()` reads `data/templates/meal_templates.json` but only the slot names are used (`index % len(slots)`), ignoring `allowed_food_groups` and gram limits. Implement deterministic group-aware slotting: extend each slot in `meal_templates.json` with `"preferred_groups": ["A","B",...]` (food group codes); assign foods to their preferred slot when possible (largest grams first, ties by food id), spill overflow into the next slot, respect `max_grams` per slot; foods with no preferred slot go to the slot with the most remaining capacity. Keep `"template_status": "DRAFT_HEURISTIC"` in the output and state in the plan JSON that slotting is heuristic. Tests: slot gram caps respected; deterministic output for fixed inputs.
6. **Plan JSON is missing nutrient totals.** `optimize()` returns `"nutrients": {}`. After verification, merge verifier totals into the plan: for every nutrient in `resolved.nutrients` plus energy: `{total, min, max, unit, met: bool}`; include `energy_total_kcal` and `pct_of_target`. Round totals to 3 decimals. The UI (Phase 3) and any consumer must be able to display "eaten vs target" without recomputing anything.
7. **`applied_rules` is mislabeled (`__main__.py:plan`).** It dumps ALL rows from `rules`. Either filter it to rules whose `applies_when` evaluated true for this patient, or rename the field `loaded_rules` and add a separate `applied_rules` list. Keep `slug`, `rationale`, `source_locator` per rule so the UI can show provenance.
8. **Read-only DB access.** `Patient.from_database`, `resolve`, `optimize`, `verify`, and `repository.py` open plain read-write connections. Switch reads to `sqlite3.connect("file:...?mode=ro", uri=True)` (keep `PRAGMA foreign_keys = ON`; it is allowed on read-only connections). Writes stay read-write (build, load-rules). Test that planning on a read-only-permission DB file succeeds.
9. **Verifier completeness (`engine/verifier.py`).** Add energy-target checking (same ±20% band the optimizer uses) and always return `totals` even when checks fail. Keep the sodium added-salt accounting (393 mg sodium per g salt, default 5 g/day) identical between optimizer and verifier — add a shared constant/test asserting they match.
10. **CLI exit codes (`__main__.py`).** `plan` exits 0 in all cases today. Make: `OK` → 0; `INCOMPLETE`/`CLINICIAN_REQUIRED` → 0 with the JSON explaining what's needed (these are valid outcomes, not errors); `INFEASIBLE_RULES`/`INFEASIBLE_PLAN`/`VERIFIER_REJECTED` → 2; usage/validation errors → 1. Document in README.
11. **`tools/` import breakage.** If any test imports from `tools/`, move the shared code into `src/dietdb/` (e.g. `dietdb/bookcheck.py`) and make `tools/*.py` thin wrappers. Tests must run from a clean checkout with just `pip install -e .` + `pytest`.
12. **Single build path + packaging.** Ensure `pip install -e .` works (src-layout is configured, but verify; add `[tool.setuptools.packages.find] where = ["src"]` if needed) so `python -m dietdb ...` works WITHOUT `PYTHONPATH=src`. Fix the `Makefile` so every target calls the same CLI entry points (no parallel build logic), and add targets: `make demo` (builds a `/tmp` draft DB, loads draft rules, runs `examples/patient_t2dm.json` through `plan`), `make app` (runs the Streamlit app from Phase 3).
13. **Dead files.** `package.json` is `{}` — delete it or fill it intentionally; deleting is fine. Remove any other dead code you find, but never delete data files or migrations.

## 4. Phase 2 — Rules, conditions, and reference data (within the no-invent rule)

1. Keep `data/rules/draft/*.json` (CKD, hypertension, T2DM) as `DRAFT`. The product's default working mode is a clearly labeled **"Draft rules — unreviewed"** mode. Every surface that shows a plan must show: (a) a global "not medical advice / draft rules" banner, and (b) per-rule `rationale` + `source_locator` from the plan JSON.
2. Load the three draft conditions via the existing `load_conditions` path so `conditions`/`condition_profiles` are populated in the working DB copy. The UI's condition checkboxes map 1:1 to `dx_type2_diabetes`, `dx_hypertension`, `dx_ckd` (+ `renal_replacement` enum when CKD is checked).
3. `baseline_reference_intakes` stays EMPTY unless the repo owner supplies ICMR-NIN RDA values. The UI must not show RDA comparisons or invent targets; if `energy_target_kcal` is absent, the engine's Mifflin-St Jeor estimate (already in `constraints._energy`) is used and labeled as an estimate.
4. Seed `diet_types` human-readable names for the codes coming from the CSV `tags` column (e.g. `VEGETARIAN`, `EGGETARIAN`, `FISHETARIAN`, `NONVEG` — check what actually appears in the data) so the UI can show friendly labels.

## 5. Phase 3 — The user product: Streamlit app

Build `app.py` at repo root (single entry point, `streamlit run app.py`). Pin `streamlit` in `requirements.txt`. Requirements:

- **Page 1 — Patient intake.** Generate the form dynamically from the `patient_variables` table (widget per `data_type`: REAL → number input, BOOLEAN → checkbox, ENUM → select from `allowed_values`, STRING → text). Sections: basics (age/sex/height/weight/activity), conditions (dx_* checkboxes; if CKD → `renal_replacement` select + optional clinician-set K/P limits), diet (dietary_pattern select, allergy multiselect populated from `allergens`), optional explicit `energy_target_kcal`. "Generate plan" button.
- **Page 2 — Plan.** Call the same Python functions the CLI uses (`Patient.from_database`, `resolve`, `optimize`, `verify`) — never reimplement logic in the UI. Render by status:
  - `OK`: status banner; foods table (name, grams, slot, `approximate` flag); per-slot meal view; nutrient totals vs min/max table with met/not-met coloring (from Phase 1 item 6); advisories list; "verified by independent recomputation" badge; download buttons (JSON + CSV).
  - `INCOMPLETE`: "We need more information" + the exact variables listed in `needs_info`.
  - `CLINICIAN_REQUIRED`: explanatory text (dialysis/transplant plans need a clinician; no plan shown).
  - `INFEASIBLE_RULES` / `INFEASIBLE_PLAN`: human-readable explanation + the conflicting constraints.
  - Always: draft-rules banner + per-rule rationale/source.
- **Page 3 — Explore foods.** Search box querying the `food_aliases` FTS index (fallback to `LIKE` if FTS is unavailable), select a food → full nutrient table (value, unit, status; show "not analysed" honestly), diet tags, allergens.
- **DB handling.** The app plans against a working copy (`data/app.db`), created by "Prepare database" (build + load draft rules + allergen inferences from Phase 1 item 3). Never plan against `data/diet.db` directly. Cache the built DB with `st.cache_resource`.
- The UI performs **zero nutrition math** — display formatting only.

Create `examples/` with at least: `patient_t2dm.json`, `patient_ckd_dialysis.json` (expect `CLINICIAN_REQUIRED`), `patient_hypertension.json`, `patient_allergic.json` (allergy_list), `patient_incomplete.json` (missing fields → `INCOMPLETE`). Use only variables that exist in `patient_variables`.

## 6. Phase 4 — Tests and hardening

- End-to-end engine tests for every `tests/fixtures/*.json` patient plus the new `examples/` patients: build tmp DB → load draft rules (draft-review semantics on the tmp copy) → plan → assert status and, for `OK`, that `verification.ok` is true and allergen/diet exclusions hold.
- Unit tests for every Phase 1 fix (pattern case-insensitivity, allergen inference + defense-in-depth warning, max-grams bound, epsilon trim + reverify, slot caps, merged nutrient totals, applied_rules filtering, read-only open, verifier energy check, CLI exit codes, rule loader rejecting unknown variables and non-APPROVED rules in production mode, `applies_when` JSON validation).
- Determinism tests kept and passing: two fresh builds → identical `get_db_hash`; repeated `plan` on same inputs → byte-identical JSON.
- Delete every `pass`-stub test; the whole suite must pass and complete in under ~5 minutes (build the DB once per session).
- If `IFCT_PDF`/`IFCT_TEXT` is not set, book-verification tests skip cleanly (already the convention — keep it).

## 7. Phase 5 — Documentation

Rewrite `README.md` to describe reality: what the product is, the draft-rules disclaimer, install (`pip install -e .`), CLI quickstart, UI quickstart, how to run tests, project layout, the IFCT 2017 license notice (electronic storage for product use requires NIN written permission — keep this), and a "Current limitations" section (draft rules, heuristic meal slotting, allergen inference is group-based, no GI/purine/FODMAP data, no cooking yields). Update `EXAMPLES.md` if any example breaks. Remove any remaining false claims, including incorrect licensing statements and wrong test counts.

## 8. Acceptance checks — ALL must pass; paste verbatim output into `FINAL_REPORT.md`

```bash
pip install -e . && pytest -q
rm -f data/diet.db && python -m dietdb build --db data/diet.db --output-hash   # run twice → identical hashes
cp data/diet.db /tmp/draft.db
python -m dietdb load-rules --db /tmp/draft.db --mode draft-review
python -m dietdb plan --db /tmp/draft.db --patient examples/patient_t2dm.json --rules-mode draft-review --out /tmp/p1.json && echo "exit=$?"
python -m dietdb plan --db /tmp/draft.db --patient examples/patient_ckd_dialysis.json --rules-mode draft-review --out /tmp/p2.json; echo "exit=$?"   # expect CLINICIAN_REQUIRED, exit 0
python -m dietdb plan --db /tmp/draft.db --patient examples/patient_allergic.json --rules-mode draft-review --out /tmp/p3.json; echo "exit=$?"       # verification ok, zero excluded-allergen foods
python -m dietdb plan --db /tmp/draft.db --patient examples/patient_incomplete.json --rules-mode draft-review --out /tmp/p4.json; echo "exit=$?"     # INCOMPLETE with needs_info
grep -rni "incorrect public-ownership" --include=*.md --include=*.py --include=*.sql .   # must print nothing
git ls-files local | wc -l        # must print 0
python -c "import sqlite3; c=sqlite3.connect('data/diet.db'); print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND sql NOT LIKE '%STRICT%' AND name NOT LIKE 'sqlite_%'\")])"  # must print []  (FTS shadow tables may appear; list them and justify)
```

Manual: `streamlit run app.py` — walk all three pages, generate a plan for the T2DM example, confirm banner/totals/slots/exports behave per Phase 3. Record anything that didn't work in FINAL_REPORT.md.

## 9. Definition of done

1. All acceptance checks pass with real pasted output.
2. Every Phase 1 bug has a regression test.
3. The Streamlit app produces a verified, slot-organized, allergen-safe draft diet plan from a form-only interaction, with honest labels everywhere.
4. No clinical value was invented; all draft rules remain `DRAFT` and visibly sourced.
5. Determinism preserved; DB runtime access read-only; FK enforced.
6. `FINAL_REPORT.md`: what was broken → what you changed (file by file), acceptance outputs, remaining limitations, assumptions made.
