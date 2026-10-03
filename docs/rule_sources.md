# DRAFT rule review sheet (Type 2 diabetes, CKD, hypertension)

Status of EVERYTHING here: **DRAFT**. Nothing is clinically reviewed. The production loader refuses these files until a clinician marks each rule APPROVED. Values were taken from guideline summaries and secondary sources I could read; primary guideline text was NOT read for any row, so every row says "verify". Recommendation numbers are left out where I could not confirm them.

## How to review (for a dietitian or doctor)
For each row: (1) open the cited guideline, (2) confirm the number, population and grade, (3) confirm the enforcement (HARD = plan may never break it; SOFT = may be relaxed with a reported penalty; ADVISORY = shown to the user, never computed), (4) change `status` to APPROVED, set `reviewed_by`, `reviewed_at`.

| Rule slug | Value | Applies when | Proposed enforcement | Source (as read) | Verify |
|---|---|---|---|---|---|
| t2dm_sodium_max_2300 | sodium <= 2,300 mg/day | type 2 diabetes | HARD | ADA Standards of Care 2026, section 5 (secondary summaries: ADA patient material, 2020-2025 slide decks) | grade, exact wording |
| t2dm_fibre_min_14_per_1000kcal | fibre >= 14 g per 1,000 kcal | type 2 diabetes | SOFT | same | same |
| t2dm_no_fixed_macro_split | none (advisory) | type 2 diabetes | ADVISORY | ADA/EASD consensus: no ideal macronutrient split | wording |
| t2dm_avoid_sugary_drinks | none (advisory) | type 2 diabetes | ADVISORY | ADA | IFCT has no beverages; text only |
| ckd_protein_max_0_8_per_kg | protein <= 0.8 g/kg actual body weight/day | CKD, no dialysis, eGFR < 60, adult | SOFT | KDIGO 2024 CKD guideline, Kidney Int 2024;105(4S):S117-S314, grade 2C (KDIGO patient takeaways PDF; NephJC review) | recommendation number; "G3-G5" population; whether to treat as cap or target |
| ckd_protein_max_1_3_per_kg | protein <= 1.3 g/kg/day | CKD, no dialysis, adult | SOFT | KDIGO 2024, Practice Point 3.3.2 (ungraded) | applies to "CKD at risk of progression", not all CKD |
| ckd_sodium_max_2000 | sodium <= 2,000 mg/day (about 5 g salt) | CKD | SOFT | KDIGO 2024, grade 2C | recommendation number |
| ckd_sodium_max_2300 | sodium <= 2,300 mg/day | CKD | HARD | KDOQI 2020 nutrition update (Am J Kidney Dis 2020;76(3 Suppl 1)) | wording |
| ckd_potassium_clinician_limit | limit supplied by clinician | CKD | HARD | KDOQI 2020: adjust to keep serum potassium normal; NO numeric intake given | needs engine support, see below |
| ckd_phosphorus_clinician_limit | limit supplied by clinician | CKD | HARD | KDOQI 2020: adjust to keep serum phosphate normal; NO numeric intake given | needs engine support |
| ckd_dialysis_needs_clinician | advisory: do not auto-plan | on dialysis | ADVISORY | KDOQI 2020 (dialysis ranges differ) | engine must route to CLINICIAN_ONLY |
| ckd_individualise_with_dietitian | advisory | CKD | ADVISORY | KDIGO 2024 practice points (plant-forward, low ultra-processed) | wording |
| htn_sodium_max_2300 | sodium <= 2,300 mg/day | hypertension | HARD | 2025 AHA/ACC high BP guideline (StatPearls NBK482514; AHA Circ Res 2021 Table 4) | class and level of evidence |
| htn_sodium_target_1500 | sodium <= 1,500 mg/day | hypertension | SOFT | same ("ideal", any reduction helps) | same |
| htn_potassium_3500_5000 | potassium 3,500-5,000 mg/day | hypertension, no CKD, eGFR >= 60 | SOFT | same; excludes CKD | ACE inhibitor/ARB and potassium-sparing diuretic use raise hyperkalaemia risk: no source read, a clinician must decide whether to add exclusions |
| htn_icmr_added_salt_5g | advisory: <= 5 g added salt | hypertension | ADVISORY | ICMR-NIN Dietary Guidelines for Indians 2024 (read via vikaspedia reproduction) | the same text also cites 2,300 mg sodium, which does not equal 5 g salt (about 2,000 mg sodium); get the primary PDF |
| htn_dash_pattern | advisory | hypertension | ADVISORY | AHA/ACC | wording |

## Alternatives (not loaded; `data/rules/draft_alternatives/`)
KDOQI 2020 protein ranges (non-diabetic CKD 3-5: 0.55-0.60 g/kg ideal weight; with diabetes: 0.6-0.8; dialysis: 1.0-1.2) and energy 25-35 kcal/kg ideal weight. They need ideal-body-weight support, which the engine does not have, and they disagree with KDIGO's 0.8 g/kg. The reviewer chooses ONE source for each nutrient; the file is deliberately outside the loaded folder.

## Known gaps (not covered, on purpose)
- No numeric potassium or phosphorus intake for CKD exists in the guidelines I read; the per-patient number must come from the kidney team.
- Fluid limits, dialysis targets, diabetes-specific carbohydrate timing for insulin or sulfonylurea users, hypoglycaemia, warfarin and vitamin K, pregnancy, children: no rules drafted.
- Saturated fat, added sugar and cholesterol limits: not drafted (no source read).
- IFCT sodium is natural sodium only. Real sodium intake is mostly added salt (NaCl is about 39% sodium: 5 g salt is about 2,000 mg sodium). Any sodium bound is meaningless unless the planner reserves a salt allowance; see ENGINE_TASKS.md.
- Conditions file: planning modes and review intervals are my proposals, not from a source.

## Files
- `data/rules/draft/{t2dm,ckd,hypertension}.json`: 17 rules, all DRAFT. They load cleanly through the repo's rule loader when status is set to APPROVED in a temporary copy (checked: nutrient names, patient variables and expression format all valid).
- `data/seed/patient_variables_conditions.json`: 6 patient variables the rules need (dx_type2_diabetes, dx_hypertension, dx_ckd, renal_replacement, clinician_max_potassium_mg_day, clinician_max_phosphorus_mg_day). The repo's seed loader reads only the two existing seed files, so the agent must be told to load this one too (see ENGINE_TASKS.md, G7).
- `data/conditions/draft_conditions.json`: three conditions (ICD-10 E11, N18, I10) and two CKD profiles. The repo has no conditions loader yet.
