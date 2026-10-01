# Diet Planning Engine - Schema Documentation

## Overview

This schema supports a diet-planning engine for patients in India with diet-restricting diseases (Type 2 diabetes, CKD, food allergies). All nutrient calculations come from deterministic database rules, not LLM memory.

## Architecture Principles

1. **Provenance First**: Every data point has a clear source
2. **Missing ≠ Zero**: Explicit tracking of NOT_DETECTED, NOT_ANALYSED, etc.
3. **Declarative Rules**: Rules are data, not executable code
4. **Idempotent Builds**: Same inputs → identical database

## Core Tables

### `sources` - Data Source Tracking
Tracks origin of all data with license and attribution info.

### `nutrients` - Nutrient Dictionary
Canonical nutrient definitions with hierarchy support.

### `foods` & `food_groups` - Food Items
Food composition data per 100g edible portion.

### `food_nutrients` - Composition Data
Nutrient values with status tracking.

### `patient_variables` - Rule Variables
The ONLY variables rules may reference, with type validation.

### `rules` - Diet Rules
Nutrient bounds, food exclusions, with tier/enforcement levels.

## Curated Tables (Initially Empty)
- `allergens` / `food_tags` - Allergen tracking
- `diet_types` - Vegetarian/vegan/Jain compatibility
- `glycemic_index` - GI/GL values
- `household_measures` - Indian portions (katori, roti)
- `preparations` - Cooking effects on nutrients

## Value Status Semantics
- **MEASURED**: Direct lab analysis
- **TRACE**: Below quantification limit
- **NOT_DETECTED**: Below detection limit
- **NOT_ANALYSED**: Not tested
- **CALCULATED**: Derived from other values

## Rule Tiers
1. **SAFETY_CRITICAL**: Hard constraints (e.g., potassium for CKD)
2. **THERAPEUTIC**: Guideline-based targets
3. **BASELINE_DEFAULT**: ICMR-NIN RDA values

## Merge Semantics
- Bounds intersect (highest min, lowest max)
- Allergen exclusions union
- THERAPEUTIC supersedes BASELINE_DEFAULT
- Infeasible → "refer to clinician"

## Gaps (IFCT Cannot Supply)
- Allergen presence (requires curation)
- Glycemic Index
- Household measures
- Regional prices
- Preparation effects