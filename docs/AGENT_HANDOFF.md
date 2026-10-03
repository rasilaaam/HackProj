# HANDOFF: finish the DietDB repository (schema + IFCT 2017 database)

You are taking over an unfinished job. Read this whole file before touching anything. Repo: https://github.com/rasilaaam/HackProj (last reviewed commit `601c3e3`). The previous agent over-claimed: its reports said things were done that were not. **Trust only what you can run.** Report only what is in the repo, with real command output.

## 1. What the project is
A diet-planning engine for patients in India with diet-restricting diseases (Type 2 diabetes, CKD, hypertension, food allergies, ...). Architecture principle, non-negotiable: **an LLM will sit on top, but must never produce a nutrient number or a safety decision.** All numbers and rules come from this database; deterministic code (later: constraint merging plus linear programming) acts on them. So correctness, provenance and honest handling of missing data matter more than speed. This is final-product code: typed, tested, documented, reproducible.

**Scope of YOUR job:** (1) the schema for diseases and foods, (2) a local SQLite database built from IFCT 2017. Do NOT build the optimizer, rule-merging engine, LLM layer or UI. Do not add features beyond the task list in section 6.

## 2. Global rules
1. **Never invent data.** No nutrient value, clinical threshold, citation or URL from memory. If something cannot be determined from the sources, record it under "Open questions" and continue with everything else.
2. **Missing is not zero.** Never turn blanks, trace or not-detected into 0 or 0.001.
3. Every fact row carries provenance (source, version, locator).
4. No `eval`/`exec`; rule conditions are declarative data.
5. Builds are deterministic (same inputs give the same logical DB hash).
6. Runtime opens the DB read-only (`mode=ro`).
7. **Copyright:** the IFCT book (NIN, Hyderabad) forbids storing it electronically for product use without NIN's written permission. NEVER commit the PDF or any text extracted from it, and never copy book tables into the repo. The only book-derived things allowed in git are column codes, units, conversion factors and match counts. Keep extracted text in a gitignored `local/` folder.
8. Do not rewrite git history or force-push. The repo owner handles history cleanup (see 4, item A1).
9. When finished, report honestly: what is done, what is not, and the output of the checks in section 7.

## 3. Verified facts (checked by the reviewer against the official book and the real package; treat as ground truth)

**Source file.** npm package `@ifct2017/compositions@2.0.0` (MIT). Tarball: `https://registry.npmjs.org/@ifct2017/compositions/-/compositions-2.0.0.tgz`; the CSV is `package/index.csv`. Required sha256: `22bb9d5072d3907af389cb77deab37a164ba5f84bf2a3eaf1a3fb274f6567ba9` (original bytes, so `.gitattributes` must keep `data/raw/** -text`; it already does). Do NOT use the GitHub `main` branch of `nodef/ifct2017`: it is AGPL-3.0 since 18 April 2025, and its CSV differs. The package CSV has 542 rows, 421 columns (207 value columns plus the matching `_e` columns plus metadata `code,name,scie,lang,grup,regn,tags`).

**Rows.** 542 = 528 foods (groups A-S) + 14 oils and fats (group T). Group counts: A24 B25 C34 D78 E68 F19 G33 H21 I2 J4 K2 L4 M15 N19 O63 P92 Q8 R7 S10 T14.
Groups: A Cereals and Millets; B Grain Legumes; C Green Leafy Vegetables; D Other Vegetables; E Fruits; F Roots and Tubers; G Condiments and Spices; H Nuts and Oil Seeds; I Sugars; J Mushrooms; K Miscellaneous Foods; L Milk and Milk Products; M Egg and Egg Products; N Poultry; O Animal Meat; P Marine Fish; Q Marine Shellfish; R Marine Mollusks; S Fresh Water Fish and Shellfish; T Edible Oils and Fats.

**Units.** The book's values are per 100 g edible portion, mean +/- SD. In the CSV:
- energy is kJ (the book: 1 kcal = 4.18 kJ, so **kcal = kJ / 4.18**);
- every mass column is stored in **grams** per 100 g, so book-printed mg = CSV x 1000 and printed ug = CSV x 1,000,000 (g stays x 1);
- amino acids are g per 100 g FOOD (the book prints g per 100 g PROTEIN; verified: CSV / protein x 100 equals the book);
- each `_e` column is the "+/-" number printed next to the mean (verified: rice calcium prints 7.49 +/- 1.26 mg and `ca_e` = 0.00126 g), so it must be converted with the same factor as its value.
- `data/mappings/unit_verification.csv` (in the repo) holds the verified factor for every column. `tools/verify_units.py` recomputes it from the book text.

**Missing data.** The book says a blank cell means "below detectable limit". The CSV has no blanks: they became 0. So a 0 on an analysed food means NOT_DETECTED, never a measured zero. Group T oils appear ONLY in book Table 12 (fatty acids): the book has no energy, protein, water, mineral, vitamin or carbohydrate data for them, so those are NOT_ANALYSED, not NOT_DETECTED. (The CSV's fat of about 100 for oils is of unverified origin.)

**Food state.** All raw except eggs: M names say "raw" (RAW) or "boiled"/"omlet" (COOKED). Poultry (N): the book says it is not raw but gives no per-entry state, so UNKNOWN (open question for NIN).

**Names.** CSV column `lang` looks like `H. Bajra; Tam. Kambu`. Language codes from the book key: A Assamese, B Bengali, G Gujarati, H Hindi, Kan Kannada, Kash Kashmiri, Kh Khasi, Kon Konkani, Mal Malayalam, M Manipuri, Mar Marathi, N Nepali, O Oriya, P Punjabi, S Sanskrit, Tam Tamil, Tel Telugu, U Urdu, Sci scientific, Common common. The CSV also has `E.` prefixes (apparently English; NOT in the book key: mark UNVERIFIED) and one stray `K.` (unrecognised: write a data_quality_flag, do not guess). `scie` holds scientific names; `tags` holds vegetarian/eggetarian/fishetarian/nonveg diet tags. Some `name`/`lang`/`scie` cells differ between the MIT package and the AGPL main branch; when in doubt prefer the book.

**Anchor values** (hand-verified in the book), A015 "Rice, raw, milled": energy 1491 kJ (356.7 kcal), protein 7.94 g, calcium 7.49 mg, phosphorus 96 mg, potassium 108 mg, sodium 2.34 mg, iron 0.65 mg, zinc 1.21 mg, vitamin K1 1.5 ug, palmitic acid (f16d0) 143 mg, phenylalanine 5.36 g per 100 g protein.

**Book structure.** 12 tables in the book: 1 proximates, 2 water-soluble vitamins, 3 fat-soluble vitamins, 4 carotenoids, 5 minerals and trace elements, 6 starch and sugars, 7 fatty acids, 8 amino acids, 9 organic acids, 10 and 11 other phytochemicals (polyphenols etc.), 12 fatty acid profile of oils. Each page header has uppercase column codes, a row of printed units and a row of names.

**Book PDF** is NOT in the repo. Ask the owner for its local path; set env `IFCT_PDF`. Extract with `pdftotext -layout "$IFCT_PDF" local/ifct_text/ifct_full.txt`.

## 4. Current state of the repo (reviewed at 601c3e3)

**Works (keep):** migrations 001-003 apply; `data/raw/ifct2017/2.0.0/index.csv` has the right checksum; wrong `data/data/` copy removed; `IFCTLoader` (`src/dietdb/ingest/ifct_loader.py`) loads 542 foods, 166 columns, 89,972 nutrient rows with correct group names and counts; `data/mappings/ifct_columns.yaml` (198 columns: 166 VERIFIED, 32 WEAK_MATCH_REVIEW_MANUALLY) agrees with the book (0 disagreements from `tools/verify_units.py`); 98-99% of loaded MEASURED values match the book (`tools/verify_db_against_book.py`); `food_allergens` fixes the broken allergen FK; all 20 food groups are right.

**Broken or missing (this is your job):**
- A1. `local/ifct_text/ifct_full.txt` (the whole book as text) is committed. Remove it from the working tree and index, add `local/` to `.gitignore`. (The owner purges history with git-filter-repo; do not force-push.)
- A2. `python -m dietdb build` (documented in README) still calls the OLD loader `ingest/ifct_simple.py`: 10 nutrients, wrong units (rice potassium stored as 0.108 "mg"), 0 aliases. The good loader is only reachable from the Makefile, whose first line is broken ("missing separator": tabs). Two build paths exist.
- A3. Energy factor is 0.2388 (should be 1/4.18); SD (`_e`) values are not converted; oils' minerals/vitamins are marked NOT_DETECTED instead of NOT_ANALYSED; 32 mapped columns are not loaded (vitamin A, D, B6, biotin, totals of omega-3/6, tocopherols, etc.), 9 more have too few values to verify.
- A4. Empty after build: scientific names (0/542), aliases (0), diet-type tags, nutrient hierarchy (`parent_id`), `patient_variables`, `allergens`, `diet_types`. Nutrient names are codes (`ifct_k`).
- A5. Source row says licence "MIT (npm package)" and `verification_status` hard-coded `VERIFIED`; README says "public domain" (false) and "13 tests, 100% passing" (false).
- A6. Schema: 0 of 30 tables STRICT; `patient_variables.max_value` is TEXT; no CHECK on enums such as `basis`; timestamp columns (`created_at`, `updated_at`, `applied_at`) still in content tables; `dishes`, `dish_ingredients`, `baseline_reference_intakes`, `build_metadata` tables missing; rule status lacks `TEST_FIXTURE`; `applies_when` not validated as JSON; no FTS sync triggers.
- A7. `DatabaseManager.get_db_hash` crashes (`no such column: rowid`); two fresh builds have different logical hashes. Rebuilding on an existing file shifts ids.
- A8. No rule loader exists (nothing rejects unknown patient variables; nothing refuses non-APPROVED rules in production mode).
- A9. Tests: 29 pass, 3 fail (`tests/test_aliases.py` imports `create_aliases` from `tools/`, not importable). 7 of 8 tests in `test_parsing.py` and 2 of 5 in `test_schema.py` are `pass` stubs. The suite takes about 77 s (build the DB once per session).
- A10. Leftovers: `src/dietdb/ingest/ifct.py` (dead, fake data), `ifct_simple.py`, `package.json` with unrelated `omniroute`, `requirements.txt` with `>=` ranges, README sections describing files that do not exist. `PRAGMA foreign_keys` is not enforced by `tools/check_integrity.py` ("Foreign keys: DISABLED").

## 5. Tools you have (in the repo; do not edit the verified factors)
- `tools/verify_units.py`: `python tools/verify_units.py --text local/ifct_text/ifct_full.txt --csv data/raw/ifct2017/2.0.0/index.csv --out /tmp/vu.csv --mapping data/mappings/ifct_columns.yaml` exits non-zero if the mapping disagrees with the book.
- `tools/verify_db_against_book.py`: `python tools/verify_db_against_book.py --db <built.db> --text local/ifct_text/ifct_full.txt` checks every MEASURED value in the built DB against the book (exit 1 if under 99%). Remaining mismatches after your fixes (roughly 400, mostly wrapped rows, rounding and amino/fatty-acid parsing in the checker itself) must be listed in your report, not hidden.
- `data/mappings/unit_verification.csv`: the verified factor per column.

## 6. Task list (do all; commit after each numbered group; keep going if one item is blocked)
1. **One build path.** `python -m dietdb build --db data/diet.db [--output-hash]` must: apply migrations to a FRESH file (refuse or delete an existing file), verify the checksum, run `IFCTLoader` with the YAML mapping, load aliases, tags and everything below. Delete `ingest/ifct.py`, `ifct_simple.py`, and the `omniroute` dependency. Fix the Makefile (tabs) to call the same command. Pin dependencies with `==` (from `pip freeze` of the environment where tests pass), mirrored in `pyproject.toml`.
2. **Loader corrections:** kcal = kJ / 4.18 (store native kJ, canonical kcal, factor in the nutrients table); convert `_e` with the same factor as its value and store as `sd`; group T: every nutrient not in book Table 12 is NOT_ANALYSED; MEASURED only for non-zero values; readable canonical names (`potassium`, `iron`, ...) with `ifct_column_code` kept; `nutrients.parent_id` from the package hierarchy (use `@ifct2017/columns` or the book; verify, do not guess); `unit_native` must be 'g' or 'kJ' as the CSV really is. Derive `food_state` per section 3.
3. **The 32 non-loaded columns plus the 9 unverified:** read each printed unit from the book header, then either verify numerically and load, or leave unloaded and list under Open questions. Never load a column whose unit you could not confirm.
4. **Foods:** scientific names from `scie`; aliases from `lang` with language codes and an FTS5 index kept in sync by triggers; diet-type tags from `tags`; `data_quality_flags` for `E.`/`K.` anomalies and for any suspicious rows.
5. **Schema:** all tables STRICT (needs SQLite 3.37+; assert it); `max_value` REAL; CHECK constraints for enums (basis, status, presence, value_status); remove content-table timestamps and put the build time only in `build_metadata`, excluded from the hash; add `dishes`, `dish_ingredients`, `baseline_reference_intakes` (empty; ICMR-NIN RDA values come from a source the owner will supply later); add `TEST_FIXTURE` to rule status; validate `applies_when` as JSON; foreign keys on in every connection.
6. **Determinism:** fix `get_db_hash` (no rowid; explicit ORDER BY on primary keys; skip virtual FTS shadow tables; skip `build_metadata`); stable ids via fixed insertion order; test that two fresh builds produce the same hash and that rebuilding never shifts ids.
7. **Rules:** seed `patient_variables` and `allergens` (EU 14 plus FSSAI list: gluten cereals, crustaceans, milk, egg, fish, peanuts, tree nuts, soybeans, sulphites, celery, mustard, sesame, lupin, molluscs) and `diet_types` from data files with citations (EU Regulation 1169/2011 Annex II; confirm the FSSAI list against its regulation text, mark UNVERIFIED if you cannot); write a rule loader that rejects rules referencing unknown patient variables and refuses non-APPROVED rules in production mode. Clinical rule values: do NOT write any; only clearly fake `TEST_FIXTURE` rules for tests.
8. **Tests:** delete every stub; real assertions for parsing, unit conversion (use the anchor values), NOT_DETECTED vs NOT_ANALYSED, no MEASURED row with value 0, group T has no energy/protein/mineral rows, group counts, 542 foods, idempotency and determinism, FTS search (`rice`, `bajra`), foreign keys, rule loader, read-only open. The PDF-dependent tests (`verify_units`, `verify_db_against_book`) run only when `IFCT_PDF`/`IFCT_TEXT` is set and are skipped otherwise. All tests pass, the suite is fast (build once per session). Fix the `tools` import problem (move shared code into `src/dietdb/`).
9. **Docs and licence:** remove every "public domain" statement. Put in README, `docs/data_sources.md` and the `sources` table: "IFCT 2017 (c) National Institute of Nutrition (ICMR), Hyderabad. Electronic storage for product use requires NIN's written permission (not yet granted). Data transcription via npm @ifct2017/compositions 2.0.0 (MIT)." Set `verification_status` honestly (for example CHECKED_AGAINST_BOOK_SAMPLE, with the date and the check's match rate), not a hard-coded VERIFIED. Correct the test counts and file lists; remove claims that are not true.

## 7. Acceptance checks (the reviewer will run these; run them yourself first and paste the output)
```
rm -f data/diet.db && python -m dietdb build --db data/diet.db --output-hash     # twice, identical hash
python -m pytest -q                                                              # all pass, no stubs
IFCT_TEXT=local/ifct_text/ifct_full.txt python -m pytest -q                      # PDF tests pass too
python tools/verify_units.py --text local/ifct_text/ifct_full.txt --csv data/raw/ifct2017/2.0.0/index.csv --out /tmp/vu.csv --mapping data/mappings/ifct_columns.yaml
python tools/verify_db_against_book.py --db data/diet.db --text local/ifct_text/ifct_full.txt
git ls-files local | wc -l        # must print 0
grep -rni "public domain" . --include=*.md --include=*.py --include=*.sql   # must print nothing
```
Also: rice A015 potassium reads 108 mg, energy 356.7 kcal, iron 0.65 mg, vitamin K1 1.5 ug from the DB; coconut oil T001 has NOT_ANALYSED energy/protein/minerals; `SELECT COUNT(*) FROM food_aliases` is greater than 0; every table is STRICT.

## 8. Final report format
1. Real counts (foods, nutrients, food_nutrients, aliases, tags) and pytest output pasted verbatim.
2. Output of each acceptance check above.
3. Which of the 41 previously unloaded columns you loaded vs left open, with the book evidence.
4. The NOT_ANALYSED and food_state lists; unmapped columns; the remaining mismatches from `verify_db_against_book.py`.
5. Open questions and every assumption you made.
Stop after this report. Do not start any curated-data work.

## 9. Context for later (NOT part of this job)
Next stages, for reference only: curated layers that IFCT does not provide (all with source and status per row): allergen tags from rules over the verified allergen lists; glycemic index from Henry et al. 2021, "Nutrition & Diabetes" (non-Western foods compendium, 940 items, includes India) plus Indian primary studies; purine levels from Kaneko et al. 2014 (Biol Pharm Bull, 270 foods) and the USDA ARS review; FODMAP data is Monash-proprietary with no public bulk source, so it is out of scope. Disease rules (clinical thresholds) will be authored by the owner from cited guidelines and reviewed by a dietitian. Product use of IFCT data needs NIN's written permission (nin@ap.nic.in, ifct2017@gmail.com per the book).
