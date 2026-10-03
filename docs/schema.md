# Database Schema

The three migrations are the source of truth. All declared tables are STRICT;
the FTS5 table is the only virtual table.

Core tables are `schema_version`, `sources`, `nutrients`, `food_groups`,
`foods`, `food_aliases`, and `food_nutrients`. Nutrient rows retain native and
canonical values, SD, status, and source provenance. Aliases are synchronized
to `food_aliases_fts` by triggers.

Curated extension tables are `allergens`, `food_allergens`, `diet_types`,
`diet_type_tags`, `purine_levels`, `food_purine_levels`, `glycemic_index`,
`household_measures`, `prices`, `preparations`, `preparation_effects`,
`dishes`, `dish_ingredients`, and `baseline_reference_intakes`.

Rule tables are `patient_variables`, `conditions`, `condition_synonyms`,
`condition_profiles`, `rules`, `rule_profiles`, and `data_quality_flags`.
`build_metadata` stores build time and hash and is excluded from logical hashes.

The later rule engine must merge nutrient bounds by intersection: highest minimum
and lowest maximum. Allergen exclusions union. A `THERAPEUTIC` rule supersedes
`BASELINE_DEFAULT` for the same nutrient. An infeasible result means “refer to
a clinician”; it is not silently relaxed.
