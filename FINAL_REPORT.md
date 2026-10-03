# DietDB Final Report

## Implemented

- Corrected test fixtures and added a session draft database fixture.
- Added read-only engine connections with foreign keys enabled.
- Added case-insensitive diet-pattern handling and patient ENUM validation.
- Added deterministic, provenance-flagged allergen inference from food groups and the reviewed seed mapping file.
- Added allergen coverage defense-in-depth, per-food gram limits, missing-energy filtering, heuristic group-aware slot assignment, nutrient totals, energy verification, and CLI exit codes.
- Added the Streamlit intake, plan, and food-exploration app, examples, packaging configuration, Make targets, and engine documentation.
- Kept all clinical draft rules at `DRAFT`; no baseline reference intake values were added.

## Real Verification Output

Focused suite:

```text
.....................                                                    [100%]
21 passed in 45.86s
```

Schema and engine focused suite:

```text
...........                                                              [100%]
11 passed in 3.72s
```

Fresh build hashes:

```text
cde100b5bc6997519d911989cea0b1c873f0eef68aa2d161e9083d69f5fc9a29
cde100b5bc6997519d911989cea0b1c873f0eef68aa2d161e9083d69f5fc9a29
```

Draft loading:

```text
RULES ARE UNREVIEWED DRAFTS: loaded 17 rules and 3 conditions
```

Example plans:

```text
{"out": "/tmp/final-plan.json", "status": "OK"}
t2d_exit=0
{"out": "/tmp/dialysis-plan.json", "status": "CLINICIAN_REQUIRED"}
dialysis_exit=0
{"out": "/tmp/allergic-plan.json", "status": "OK"}
allergic_exit=0
{"out": "/tmp/incomplete-plan.json", "status": "INCOMPLETE"}
incomplete_exit=0
```

The allergic plan verified successfully and contained no inferred milk-allergen food. The incomplete plan reported missing information rather than producing a plan.

Schema and repository checks:

```text
['food_aliases_fts', 'food_aliases_fts_data', 'food_aliases_fts_idx', 'food_aliases_fts_docsize', 'food_aliases_fts_config']
136
0
```

The first line lists only FTS virtual-table shadow tables; all ordinary tables are STRICT. The second line is the deterministic inferred `food_allergens` row count. The final line confirms no tracked `local/` files.

## Remaining Verification Gap

The complete build-backed `pytest -q` run did not return a final summary in the managed shell; its captured log stopped at the initial five tests while the IFCT fixture build was running. The fast non-build suite and focused engine/schema suites passed as recorded above. The environment also did not provide `pip` inside the Nix shell, so `pip install -e .` was not executable there; the packaging metadata and editable-install configuration are present for a normal Python environment.

The Streamlit app was syntax-checked but not manually opened in a browser in this environment.
