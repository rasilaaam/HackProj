# DietDB

DietDB is a deterministic Indian food-composition and diet-plan suggestion engine. Nutrient values and safety decisions come only from the SQLite database and deterministic Python code. Draft rules are unreviewed and plans are not medical advice.

## Install

```bash
python -m pip install -e .
```

## Build And Test

```bash
python -m dietdb build --db data/diet.db
python -m pytest -q
```

The build loads 542 IFCT foods, 166 nutrients, and 89,972 nutrient rows from the pinned IFCT transcription. Fresh builds are content-hashed and deterministic.

The repository currently collects 58 tests. The latest Gemini and production-guard regression run passed 5 tests. Rules remain unreviewed draft content and every plan surface must be treated as not medical advice.

## How Rules Become Approved

Draft JSON rules are never promoted automatically. A qualified reviewer must inspect the source and rationale, then run:

```bash
python tools/approve_rules.py --reviewer "Name, credential" \
  --slugs rule_slug_one rule_slug_two --confirm-reviewed
```

The tool records `reviewed_by` and `reviewed_at` in the rule JSON and appends an audit line to `docs/approvals.md`. The application uses production mode only when approved rules are present; otherwise it labels the plan as using unreviewed drafts. No rules are approved by default.

## Optional Gemini Assistance

Set `GEMINI_API_KEY` to enable report extraction and plan explanations. `GEMINI_MODEL` selects the model and defaults to `gemini-2.0-flash`; set this to a model available to your key. The model is optional, never supplies accepted safety decisions, and all extracted patient values are validated against the database.

## Draft Rules And Plans

Draft clinical rules remain `DRAFT`. Load them into a working copy, never the canonical database:

```bash
cp data/diet.db /tmp/draft.db
python -m dietdb load-rules --db /tmp/draft.db --mode draft-review
python -m dietdb plan --db /tmp/draft.db --patient examples/patient_t2dm.json \
  --rules-mode draft-review --out /tmp/plan.json
```

The CLI reports `OK`, `INCOMPLETE`, `CLINICIAN_REQUIRED`, `INFEASIBLE_RULES`, `INFEASIBLE_PLAN`, or `VERIFIER_REJECTED`. `streamlit run app.py` starts the three-page intake, plan, and food-exploration UI.

## Layout

- `src/dietdb/ingest/`: IFCT loader and deterministic reference data
- `src/dietdb/engine/`: constraints, optimizer, and independent verifier
- `data/rules/draft/`: explicitly unreviewed rule drafts
- `data/seed/`: version-controlled reference and allergen-inference inputs
- `migrations/`: STRICT SQLite schema
- `examples/`: patient input examples
- `docs/engine.md`: pipeline and deliberate limitations

## Current Limitations

Rules are draft and require clinical review. Meal slotting is heuristic. Allergen inference is group/name based and should be reviewed. There are no GI, purine, or FODMAP datasets, and no cooking yields or price objective. Baseline reference intakes remain empty until supplied by the owner.

## Data And Licence

IFCT 2017 (c) National Institute of Nutrition (ICMR), Hyderabad. Electronic storage for product use requires NIN's written permission (not yet granted). The data transcription package is pinned separately under its MIT licence; see `docs/data_sources.md`.
