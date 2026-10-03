-- Migration 001: Initial schema for diet planning engine
-- Creates core tables for nutrients, foods, diseases, and rules

PRAGMA foreign_keys = ON;

-- ============================================================
-- SCHEMA VERSION TRACKING
-- ============================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    script_name TEXT NOT NULL,
    checksum TEXT NOT NULL
) STRICT;

-- ============================================================
-- DATA SOURCES
-- ============================================================
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    version TEXT,
    year INTEGER,
    publisher TEXT,
    license TEXT,
    attribution TEXT,
    source_url TEXT,
    local_path TEXT,
    checksum TEXT,
    verification_status TEXT DEFAULT 'UNVERIFIED',
    notes TEXT
) STRICT;

-- ============================================================
-- NUTRIENTS DICTIONARY
-- ============================================================
CREATE TABLE IF NOT EXISTS nutrients (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    category TEXT NOT NULL,
    canonical_unit TEXT NOT NULL,
    ifct_column_code TEXT,
    parent_id INTEGER,
    is_constrainable INTEGER DEFAULT 0,
    conversion_factor REAL,
    native_unit TEXT,
    sort_order INTEGER DEFAULT 0,
    FOREIGN KEY (parent_id) REFERENCES nutrients(id),
    CHECK (is_constrainable IN (0, 1))
) STRICT;

-- ============================================================
-- FOOD GROUPS
-- ============================================================
CREATE TABLE IF NOT EXISTS food_groups (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    parent_id INTEGER,
    level INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (parent_id) REFERENCES food_groups(id)
) STRICT;

-- ============================================================
-- FOODS
-- ============================================================
CREATE TABLE IF NOT EXISTS foods (
    id INTEGER PRIMARY KEY,
    source_code TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    english_name TEXT NOT NULL,
    scientific_name TEXT,
    food_group_id INTEGER,
    edible_portion_pct REAL,
    food_state TEXT NOT NULL DEFAULT 'RAW',
    reference_basis TEXT NOT NULL DEFAULT 'PER_100G_EDIBLE',
    notes TEXT,
    quality_flag TEXT,
    UNIQUE(source_code, source_id),
    FOREIGN KEY (source_id) REFERENCES sources(id),
    FOREIGN KEY (food_group_id) REFERENCES food_groups(id)
) STRICT;

-- ============================================================
-- FOOD ALIASES (for search)
-- ============================================================
CREATE TABLE IF NOT EXISTS food_aliases (
    id INTEGER PRIMARY KEY,
    food_id INTEGER NOT NULL,
    alias TEXT NOT NULL,
    language TEXT NOT NULL,
    script TEXT NOT NULL DEFAULT 'Latn',
    alias_type TEXT NOT NULL DEFAULT 'COMMON',
    is_preferred INTEGER DEFAULT 0,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE
) STRICT;

CREATE VIRTUAL TABLE IF NOT EXISTS food_aliases_fts USING fts5(
    alias,
    content='food_aliases',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS food_aliases_ai AFTER INSERT ON food_aliases BEGIN
    INSERT INTO food_aliases_fts(rowid, alias) VALUES (new.id, new.alias);
END;
CREATE TRIGGER IF NOT EXISTS food_aliases_ad AFTER DELETE ON food_aliases BEGIN
    INSERT INTO food_aliases_fts(food_aliases_fts, rowid, alias)
    VALUES ('delete', old.id, old.alias);
END;
CREATE TRIGGER IF NOT EXISTS food_aliases_au AFTER UPDATE OF alias ON food_aliases BEGIN
    INSERT INTO food_aliases_fts(food_aliases_fts, rowid, alias)
    VALUES ('delete', old.id, old.alias);
    INSERT INTO food_aliases_fts(rowid, alias) VALUES (new.id, new.alias);
END;

-- ============================================================
-- FOOD NUTRIENTS (core compositional data)
-- ============================================================
CREATE TABLE IF NOT EXISTS food_nutrients (
    food_id INTEGER NOT NULL,
    nutrient_id INTEGER NOT NULL,
    value_native REAL,
    unit_native TEXT NOT NULL,
    value_canonical REAL,
    canonical_unit TEXT NOT NULL,
    sd REAL,
    value_status TEXT NOT NULL CHECK(value_status IN (
        'MEASURED', 'TRACE', 'NOT_DETECTED', 'NOT_ANALYSED', 'CALCULATED'
    )),
    raw_text TEXT,
    source_id INTEGER NOT NULL,
    source_row INTEGER,
    PRIMARY KEY (food_id, nutrient_id),
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
    FOREIGN KEY (nutrient_id) REFERENCES nutrients(id),
    FOREIGN KEY (source_id) REFERENCES sources(id),
    CHECK (value_canonical >= 0 OR value_status IN ('NOT_DETECTED', 'NOT_ANALYSED'))
) STRICT;

CREATE TABLE IF NOT EXISTS build_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;
