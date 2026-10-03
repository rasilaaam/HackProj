# Database Schema

The three migrations are the source of truth. All declared tables are STRICT;
the FTS5 table is the only virtual table.

## Tables and columns

- `schema_version`: `version`, `script_name`, `checksum`; migration identity.
- `sources`: `id`, `slug`, `name`, `description`, `version`, `year`, `publisher`, `license`, `attribution`, `source_url`, `local_path`, `checksum`, `verification_status`, `notes`; provenance.
- `nutrients`: `id`, `canonical_name`, `display_name`, `category`, `canonical_unit`, `ifct_column_code`, `parent_id`, `is_constrainable`, `conversion_factor`, `native_unit`, `sort_order`; nutrient dictionary.
- `food_groups`: `id`, `code`, `name`, `description`, `parent_id`, `level`; food taxonomy.
- `foods`: `id`, `source_code`, `source_id`, `english_name`, `scientific_name`, `food_group_id`, `edible_portion_pct`, `food_state`, `reference_basis`, `notes`, `quality_flag`; food identity.
- `food_aliases`: `id`, `food_id`, `alias`, `language`, `script`, `alias_type`, `is_preferred`; multilingual search names.
- `food_nutrients`: `food_id`, `nutrient_id`, `value_native`, `unit_native`, `value_canonical`, `canonical_unit`, `sd`, `value_status`, `raw_text`, `source_id`, `source_row`; measured composition and provenance.
- `allergens`: `id`, `code`, `name`, `description`; allergen vocabulary.
- `food_allergens`: `id`, `food_id`, `allergen_id`, `presence`, `source_id`, `assessed_at`, `notes`; later curated allergen assessments.
- `diet_types`: `id`, `code`, `name`, `description`; diet vocabulary.
- `diet_type_tags`: `id`, `food_id`, `diet_type_id`, `is_compatible`, `source_id`; source diet tags.
- `purine_levels`, `food_purine_levels`, `glycemic_index`, `household_measures`, `prices`, `preparations`, `preparation_effects`; empty curated extension tables with their migration-defined columns.
- `dishes`: `id`, `slug`, `name_en`, `region`, `diet_type`, `meal_slot`, `yield_factor`, `source_id`, `status`, `notes`; future dish definitions.
- `dish_ingredients`: `id`, `dish_id`, `food_id`, `grams_raw`, `preparation_id`; dish composition links.
- `baseline_reference_intakes`: `id`, `nutrient_id`, `sex`, `age_min_years`, `age_max_years`, `physiological_state`, `activity_level`, `min_value`, `max_value`, `target_value`, `unit`, `basis`, `source_id`, `source_locator`, `status`; empty owner-supplied reference layer.
- `build_metadata`: `key`, `value`; build hash/time excluded from content hashing.
- `patient_variables`: `id`, `variable_name`, `display_name`, `data_type`, `unit`, `allowed_values`, `min_value`, `max_value`, `source`, `description`; rule input vocabulary.
- `conditions`, `condition_synonyms`, `condition_profiles`: migration-defined condition identity and profile columns.
- `rules`: `id`, `slug`, `name`, `kind`, `target_type`, `target_ref`, `min_value`, `max_value`, `target_value`, `tolerance`, `unit`, `basis`, `tier`, `enforcement`, `applies_when`, `rationale`, `source_id`, `source_locator`, `evidence_grade`, `status`, `reviewed_by`, `reviewed_at`, `version`, `valid_from`, `valid_to`; declarative constraints.
- `rule_profiles`: `rule_id`, `condition_profile_id`; rule/profile links.
- `data_quality_flags`: `id`, `table_name`, `record_id`, `flag_type`, `severity`, `description`, `field_name`, `raw_value`, `expected_value`, `resolved`, `resolution_notes`, `flagged_by`; deterministic data warnings.

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
