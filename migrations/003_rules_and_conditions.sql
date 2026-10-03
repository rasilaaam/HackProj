-- Migration 003: Patient variables, conditions, and diet rules
-- Extends schema with patient variables and disease management tables

-- ============================================================
-- PATIENT VARIABLES (the ONLY variables rules may reference)
-- ============================================================
CREATE TABLE IF NOT EXISTS patient_variables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variable_name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    data_type TEXT NOT NULL CHECK(data_type IN ('INTEGER', 'REAL', 'BOOLEAN', 'STRING', 'ENUM')),
    unit TEXT,
    allowed_values TEXT,
    min_value REAL,
    max_value REAL,
    source TEXT NOT NULL,
    description TEXT
);

-- ============================================================
-- MEDICAL CONDITIONS/DISEASES
-- ============================================================
CREATE TABLE IF NOT EXISTS conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    icd10_code TEXT,
    category TEXT NOT NULL,
    chronicity TEXT NOT NULL CHECK(chronicity IN (
        'LIFELONG_INCURABLE', 'LIFELONG_MANAGEABLE', 'REVERSIBLE', 
        'CURABLE', 'SELF_LIMITING', 'MAY_BE_OUTGROWN'
    )),
    planning_mode TEXT NOT NULL CHECK(planning_mode IN (
        'AUTO_PLAN', 'AUTO_PLAN_WITH_CLINICIAN_CONFIRMATION', 'CLINICIAN_ONLY_NO_AUTOPLAN'
    )),
    review_interval_months INTEGER DEFAULT 12,
    eligibility_expression TEXT,
    description TEXT,
    source_id INTEGER,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS condition_synonyms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id INTEGER NOT NULL,
    synonym TEXT NOT NULL,
    synonym_type TEXT DEFAULT 'ABBREVIATION',
    FOREIGN KEY (condition_id) REFERENCES conditions(id) ON DELETE CASCADE,
    UNIQUE(condition_id, synonym)
);

-- Condition Profiles (stages/variants)
CREATE TABLE IF NOT EXISTS condition_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id INTEGER NOT NULL,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    stage_or_variant TEXT,
    selector_expression TEXT NOT NULL,
    exclusivity_group TEXT,
    priority INTEGER DEFAULT 0,
    FOREIGN KEY (condition_id) REFERENCES conditions(id) ON DELETE CASCADE,
    UNIQUE(condition_id, slug)
);

-- ============================================================
-- DIET RULES
-- ============================================================
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN (
        'NUTRIENT_BOUND', 'NUTRIENT_TARGET', 'FOOD_EXCLUDE', 
        'FOOD_LIMIT', 'FOOD_PREFER', 'DISTRIBUTION', 
        'FLUID_LIMIT', 'RATIO', 'PREPARATION_REQUIRED',
        'DRUG_FOOD_INTERACTION', 'ADVISORY_TEXT'
    )),
    target_type TEXT NOT NULL CHECK(target_type IN (
        'NUTRIENT', 'FOOD', 'FOOD_GROUP', 'TAG', 'ALLERGEN', 'MEDICATION_CLASS'
    )),
    target_ref TEXT NOT NULL,
    min_value REAL,
    max_value REAL,
    target_value REAL,
    tolerance REAL,
    unit TEXT,
    basis TEXT NOT NULL CHECK(basis IN (
        'PER_DAY', 'PER_MEAL', 'PER_WEEK', 'PER_KG_ACTUAL_WEIGHT',
        'PER_KG_IDEAL_WEIGHT', 'PCT_OF_ENERGY', 'PER_1000_KCAL'
    )),
    tier TEXT NOT NULL CHECK(tier IN ('SAFETY_CRITICAL', 'THERAPEUTIC', 'BASELINE_DEFAULT')),
    enforcement TEXT NOT NULL CHECK(enforcement IN ('HARD', 'SOFT', 'ADVISORY')),
    applies_when TEXT NOT NULL CHECK(json_valid(applies_when)),
    rationale TEXT NOT NULL,
    source_id INTEGER,
    source_locator TEXT,
    evidence_grade TEXT,
    status TEXT NOT NULL CHECK(status IN ('DRAFT', 'CLINICALLY_REVIEWED', 'APPROVED', 'DEPRECATED', 'TEST_FIXTURE')),
    reviewed_by TEXT,
    reviewed_at TEXT,
    version INTEGER DEFAULT 1,
    valid_from TEXT,
    valid_to TEXT,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    CHECK (min_value IS NULL OR max_value IS NULL OR min_value <= max_value)
);

CREATE TABLE IF NOT EXISTS rule_profiles (
    rule_id INTEGER NOT NULL,
    condition_profile_id INTEGER NOT NULL,
    PRIMARY KEY (rule_id, condition_profile_id),
    FOREIGN KEY (rule_id) REFERENCES rules(id) ON DELETE CASCADE,
    FOREIGN KEY (condition_profile_id) REFERENCES condition_profiles(id) ON DELETE CASCADE
);

-- ============================================================
-- DATA QUALITY FLAGS
-- ============================================================
CREATE TABLE IF NOT EXISTS data_quality_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    flag_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('INFO', 'WARNING', 'ERROR')),
    description TEXT NOT NULL,
    field_name TEXT,
    raw_value TEXT,
    expected_value TEXT,
    resolved INTEGER DEFAULT 0,
    resolution_notes TEXT,
    flagged_at TEXT NOT NULL DEFAULT (datetime('now')),
    flagged_by TEXT DEFAULT 'SYSTEM'
);

-- ============================================================
-- INDICES FOR PERFORMANCE
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_rules_status ON rules(status);
CREATE INDEX IF NOT EXISTS idx_rules_condition ON rule_profiles(condition_profile_id);
CREATE INDEX IF NOT EXISTS idx_data_quality_unresolved ON data_quality_flags(table_name, record_id) WHERE resolved = 0;
CREATE INDEX IF NOT EXISTS idx_condition_profiles_exclusivity ON condition_profiles(exclusivity_group);
