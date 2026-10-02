# DietDB - Complete Schema (26 Tables)

Your database has **26 tables** across 3 migrations. Here's what you built:

## Migration 1: Core Data (8 Tables)

| Table | Purpose | Status |
|-------|---------|--------|
| `schema_version` | Track migrations | System |
| `sources` | Data sources (IFCT 2017) | 1 row ✅ |
| `nutrients` | Nutrient master list | 10 rows ✅ |
| `food_groups` | Food categories | 4 rows ✅ |
| `foods` | All foods | 542 rows ✅ |
| `food_aliases` | Alternative food names | 0 rows (ready) |
| `food_aliases_fts` | Full-text search | System |
| `food_nutrients` | Nutrient data | 5,420 rows ✅ |

### Key Tables Explained

**nutrients** - Tracks 10 core nutrients:
- Energy (kcal)
- Protein, Total Fat, Carbohydrate, Dietary Fibre (macros)
- Calcium, Iron, Phosphorus, Potassium, Sodium (minerals)

**food_nutrients** - 5,420 measurements with status:
- MEASURED - Directly measured
- TRACE - Trace amount
- NOT_DETECTED - Below detection limit
- NOT_ANALYSED - Not tested
- CALCULATED - Derived

---

## Migration 2: Curated Data (11 Tables)

| Table | Purpose | Status |
|-------|---------|--------|
| `allergens` | Allergen master list | 0 rows |
| `food_tags` | Track allergen presence | 0 rows |
| `diet_types` | Diet type definitions | 0 rows |
| `diet_type_tags` | Food-to-diet compatibility | 0 rows |
| `purine_levels` | Purine content categories | 0 rows |
| `food_purine_levels` | Purine per food | 0 rows |
| `glycemic_index` | GI/GL values | 0 rows |
| `household_measures` | Cup, spoon, piece to grams | 0 rows |
| `prices` | Regional food prices (INR) | 0 rows |
| `preparations` | Cooking methods | 0 rows |
| `preparation_effects` | Nutrient retention % | 0 rows |

**For Future**: Allergens, diet compatibility, cooking effects, prices

---

## Migration 3: Rules & Conditions (7 Tables)

| Table | Purpose | Status |
|-------|---------|--------|
| `patient_variables` | Allowed rule variables | 0 rows |
| `conditions` | Diseases (T2DM, CKD, Gout) | 0 rows |
| `condition_synonyms` | Disease aliases | 0 rows |
| `condition_profiles` | Disease stages | 0 rows |
| `rules` | Diet rules/constraints | 0 rows |
| `rule_profiles` | Rule-to-condition links | 0 rows |
| `data_quality_flags` | Quality tracking | 0 rows |

**For Future**: Define conditions, patient variables, and diet rules

---

## Quick Examples

### Query Structure

```
foods (542) ← → food_nutrients (5,420) ← → nutrients (10)
                ↓
            sources (1 - IFCT 2017)
```

### Sample Queries You Can Run

Find high-protein foods:
```sql
SELECT f.english_name, fn.value_canonical
FROM foods f
JOIN food_nutrients fn ON f.id = fn.food_id
JOIN nutrients n ON fn.nutrient_id = n.id
WHERE n.canonical_name = 'protein'
ORDER BY fn.value_canonical DESC LIMIT 10;
```

Check data quality:
```sql
SELECT value_status, COUNT(*)
FROM food_nutrients
GROUP BY value_status;
```

---

## Full Table Count

**Populated**: 8 tables with data  
**Empty/Ready**: 18 tables waiting for data  
**Total**: 26 tables  

Everything is schema-complete and ready to extend!
