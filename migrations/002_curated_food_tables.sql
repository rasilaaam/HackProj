-- Migration 002: Curated food tables and patient variables
-- Extends initial schema with curated data tables

-- ============================================================
-- CURATED FOOD TABLES (initially empty, populated by curation)
-- ============================================================

-- Allergen presence/absence tracking
CREATE TABLE IF NOT EXISTS allergens (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS food_allergens (
    id INTEGER PRIMARY KEY,
    food_id INTEGER NOT NULL,
    allergen_id INTEGER NOT NULL,
    presence TEXT NOT NULL CHECK(presence IN ('PRESENT', 'ABSENT', 'UNKNOWN')),
    source_id INTEGER,
    assessed_at TEXT,
    notes TEXT,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (allergen_id) REFERENCES allergens(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(food_id, allergen_id)
) STRICT;

-- Diet type compatibility
CREATE TABLE IF NOT EXISTS diet_types (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS diet_type_tags (
    id INTEGER PRIMARY KEY,
    food_id INTEGER NOT NULL,
    diet_type_id INTEGER NOT NULL,
    is_compatible INTEGER NOT NULL DEFAULT 1,
    source_id INTEGER,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (diet_type_id) REFERENCES diet_types(id),
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(food_id, diet_type_id)
) STRICT;

-- Purine content levels
CREATE TABLE IF NOT EXISTS purine_levels (
    id INTEGER PRIMARY KEY,
    level TEXT UNIQUE NOT NULL,
    description TEXT,
    mg_per_100g_min REAL,
    mg_per_100g_max REAL
) STRICT;

CREATE TABLE IF NOT EXISTS food_purine_levels (
    food_id INTEGER PRIMARY KEY,
    purine_level_id INTEGER NOT NULL,
    mg_per_100g REAL,
    source_id INTEGER,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (purine_level_id) REFERENCES purine_levels(id),
    FOREIGN KEY (source_id) REFERENCES sources(id)
) STRICT;

-- Glycemic Index
CREATE TABLE IF NOT EXISTS glycemic_index (
    food_id INTEGER PRIMARY KEY,
    gi_value INTEGER,
    gl_basis_serving REAL,
    gl_basis_reference REAL DEFAULT 50,
    method TEXT,
    source_id INTEGER,
    measured_at TEXT,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id)
) STRICT;

-- Household Measures
CREATE TABLE IF NOT EXISTS household_measures (
    id INTEGER PRIMARY KEY,
    food_id INTEGER NOT NULL,
    measure_type TEXT NOT NULL,
    grams REAL NOT NULL,
    volume_ml REAL,
    description TEXT,
    source_id INTEGER,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(food_id, measure_type, description)
) STRICT;

-- Regional Prices (for affordability calculations)
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY,
    food_id INTEGER NOT NULL,
    price_inr_per_kg REAL NOT NULL,
    region TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    source_id INTEGER,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(food_id, region, as_of_date)
) STRICT;

-- Cooking Preparations
CREATE TABLE IF NOT EXISTS preparations (
    id INTEGER PRIMARY KEY,
    food_id INTEGER NOT NULL,
    method TEXT NOT NULL,
    weight_yield_factor REAL,
    description TEXT,
    source_id INTEGER,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(food_id, method)
) STRICT;

CREATE TABLE IF NOT EXISTS dishes (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name_en TEXT NOT NULL,
    region TEXT,
    diet_type TEXT,
    meal_slot TEXT NOT NULL CHECK(meal_slot IN ('breakfast', 'lunch', 'dinner', 'snack', 'any')),
    yield_factor REAL NOT NULL CHECK(yield_factor > 0),
    source_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (source_id) REFERENCES sources(id)
) STRICT;

CREATE TABLE IF NOT EXISTS dish_ingredients (
    id INTEGER PRIMARY KEY,
    dish_id INTEGER NOT NULL,
    food_id INTEGER NOT NULL,
    grams_raw REAL NOT NULL CHECK(grams_raw > 0),
    preparation_id INTEGER,
    UNIQUE(dish_id, food_id, preparation_id),
    FOREIGN KEY (dish_id) REFERENCES dishes(id) ON DELETE CASCADE,
    FOREIGN KEY (food_id) REFERENCES foods(id),
    FOREIGN KEY (preparation_id) REFERENCES preparations(id)
) STRICT;

CREATE TABLE IF NOT EXISTS baseline_reference_intakes (
    id INTEGER PRIMARY KEY,
    nutrient_id INTEGER NOT NULL,
    sex TEXT NOT NULL CHECK(sex IN ('male', 'female', 'any')),
    age_min_years REAL,
    age_max_years REAL,
    physiological_state TEXT NOT NULL CHECK(physiological_state IN ('none', 'pregnant', 'lactating')),
    activity_level TEXT,
    min_value REAL,
    max_value REAL,
    target_value REAL,
    unit TEXT NOT NULL,
    basis TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    source_locator TEXT,
    status TEXT NOT NULL,
    FOREIGN KEY (nutrient_id) REFERENCES nutrients(id),
    FOREIGN KEY (source_id) REFERENCES sources(id)
) STRICT;

CREATE TABLE IF NOT EXISTS preparation_effects (
    id INTEGER PRIMARY KEY,
    preparation_id INTEGER NOT NULL,
    nutrient_id INTEGER NOT NULL,
    retention_factor REAL NOT NULL,
    source_id INTEGER,
    FOREIGN KEY (preparation_id) REFERENCES preparations(id) ON DELETE CASCADE,
    FOREIGN KEY (nutrient_id) REFERENCES nutrients(id),
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(preparation_id, nutrient_id)
) STRICT;

-- ============================================================
-- INDICES FOR PERFORMANCE
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_foods_source_id ON foods(source_id);
CREATE INDEX IF NOT EXISTS idx_foods_group ON foods(food_group_id);
CREATE INDEX IF NOT EXISTS idx_food_nutrients_food ON food_nutrients(food_id);
CREATE INDEX IF NOT EXISTS idx_food_nutrients_nutrient ON food_nutrients(nutrient_id);
CREATE INDEX IF NOT EXISTS idx_food_aliases_food ON food_aliases(food_id);
CREATE INDEX IF NOT EXISTS idx_food_allergens_food ON food_allergens(food_id);
CREATE INDEX IF NOT EXISTS idx_diet_type_tags_food ON diet_type_tags(food_id);
