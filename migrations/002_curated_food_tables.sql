-- Migration 002: Curated food tables and patient variables
-- Extends initial schema with curated data tables

-- ============================================================
-- CURATED FOOD TABLES (initially empty, populated by curation)
-- ============================================================

-- Allergen presence/absence tracking
CREATE TABLE IF NOT EXISTS allergens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS food_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food_id INTEGER NOT NULL,
    presence TEXT NOT NULL CHECK(presence IN ('PRESENT', 'ABSENT', 'UNKNOWN')),
    source_id INTEGER,
    assessed_at TEXT,
    notes TEXT,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    FOREIGN KEY (id) REFERENCES allergens(id) ON DELETE CASCADE,
    UNIQUE(food_id, id)
);

-- Diet type compatibility
CREATE TABLE IF NOT EXISTS diet_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS diet_type_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food_id INTEGER NOT NULL,
    diet_type_id INTEGER NOT NULL,
    is_compatible INTEGER NOT NULL DEFAULT 1,
    source_id INTEGER,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (diet_type_id) REFERENCES diet_types(id),
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(food_id, diet_type_id)
);

-- Purine content levels
CREATE TABLE IF NOT EXISTS purine_levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT UNIQUE NOT NULL,
    description TEXT,
    mg_per_100g_min REAL,
    mg_per_100g_max REAL
);

CREATE TABLE IF NOT EXISTS food_purine_levels (
    food_id INTEGER PRIMARY KEY,
    purine_level_id INTEGER NOT NULL,
    mg_per_100g REAL,
    source_id INTEGER,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (purine_level_id) REFERENCES purine_levels(id),
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

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
);

-- Household Measures
CREATE TABLE IF NOT EXISTS household_measures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food_id INTEGER NOT NULL,
    measure_type TEXT NOT NULL,
    grams REAL NOT NULL,
    volume_ml REAL,
    description TEXT,
    source_id INTEGER,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(food_id, measure_type, description)
);

-- Regional Prices (for affordability calculations)
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food_id INTEGER NOT NULL,
    price_inr_per_kg REAL NOT NULL,
    region TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    source_id INTEGER,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(food_id, region, as_of_date)
);

-- Cooking Preparations
CREATE TABLE IF NOT EXISTS preparations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food_id INTEGER NOT NULL,
    method TEXT NOT NULL,
    weight_yield_factor REAL,
    description TEXT,
    source_id INTEGER,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(food_id, method)
);

CREATE TABLE IF NOT EXISTS preparation_effects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preparation_id INTEGER NOT NULL,
    nutrient_id INTEGER NOT NULL,
    retention_factor REAL NOT NULL,
    source_id INTEGER,
    FOREIGN KEY (preparation_id) REFERENCES preparations(id) ON DELETE CASCADE,
    FOREIGN KEY (nutrient_id) REFERENCES nutrients(id),
    FOREIGN KEY (source_id) REFERENCES sources(id),
    UNIQUE(preparation_id, nutrient_id)
);