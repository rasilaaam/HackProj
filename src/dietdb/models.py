"""
Pydantic models for DietDB
Core data structures for the diet planning engine
"""

from enum import Enum
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# ============================================================
# ENUMERATIONS
# ============================================================

class ValueStatus(str, Enum):
    """Status of a nutrient measurement"""
    MEASURED = "MEASURED"
    TRACE = "TRACE"
    NOT_DETECTED = "NOT_DETECTED"
    NOT_ANALYSED = "NOT_ANALYSED"
    CALCULATED = "CALCULATED"


class FoodState(str, Enum):
    """State of food as consumed"""
    RAW = "RAW"
    COOKED = "COOKED"
    PROCESSED = "PROCESSED"
    DRIED = "DRIED"
    FERMENTED = "FERMENTED"


class NutrientCategory(str, Enum):
    """Nutrient classification"""
    ENERGY = "ENERGY"
    MACRO = "MACRO"
    MINERAL = "MINERAL"
    VITAMIN = "VITAMIN"
    AMINO_ACID = "AMINO_ACID"
    FATTY_ACID = "FATTY_ACID"
    OTHER = "OTHER"


class AllergenPresence(str, Enum):
    """Allergen presence tracking"""
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


class RuleKind(str, Enum):
    """Classification of diet rules"""
    NUTRIENT_BOUND = "NUTRIENT_BOUND"
    NUTRIENT_TARGET = "NUTRIENT_TARGET"
    FOOD_EXCLUDE = "FOOD_EXCLUDE"
    FOOD_LIMIT = "FOOD_LIMIT"
    FOOD_PREFER = "FOOD_PREFER"
    DISTRIBUTION = "DISTRIBUTION"
    FLUID_LIMIT = "FLUID_LIMIT"
    RATIO = "RATIO"
    PREPARATION_REQUIRED = "PREPARATION_REQUIRED"
    DRUG_FOOD_INTERACTION = "DRUG_FOOD_INTERACTION"
    ADVISORY_TEXT = "ADVISORY_TEXT"


class RuleTargetType(str, Enum):
    """What a rule targets"""
    NUTRIENT = "NUTRIENT"
    FOOD = "FOOD"
    FOOD_GROUP = "FOOD_GROUP"
    TAG = "TAG"
    ALLERGEN = "ALLERGEN"
    MEDICATION_CLASS = "MEDICATION_CLASS"


class RuleBasis(str, Enum):
    """Measurement basis for a rule"""
    PER_DAY = "PER_DAY"
    PER_MEAL = "PER_MEAL"
    PER_WEEK = "PER_WEEK"
    PER_KG_ACTUAL_WEIGHT = "PER_KG_ACTUAL_WEIGHT"
    PER_KG_IDEAL_WEIGHT = "PER_KG_IDEAL_WEIGHT"
    PCT_OF_ENERGY = "PCT_OF_ENERGY"
    PER_1000_KCAL = "PER_1000_KCAL"


class RuleTier(str, Enum):
    """Priority tier for rule application"""
    SAFETY_CRITICAL = "SAFETY_CRITICAL"
    THERAPEUTIC = "THERAPEUTIC"
    BASELINE_DEFAULT = "BASELINE_DEFAULT"


class RuleEnforcement(str, Enum):
    """How strictly a rule is enforced"""
    HARD = "HARD"
    SOFT = "SOFT"
    ADVISORY = "ADVISORY"


class RuleStatus(str, Enum):
    """Lifecycle status of a rule"""
    DRAFT = "DRAFT"
    CLINICALLY_REVIEWED = "CLINICALLY_REVIEWED"
    APPROVED = "APPROVED"
    DEPRECATED = "DEPRECATED"
    TEST_FIXTURE = "TEST_FIXTURE"


class Chronicity(str, Enum):
    """Clinical chronicity of a condition"""
    LIFELONG_INCURABLE = "LIFELONG_INCURABLE"
    LIFELONG_MANAGEABLE = "LIFELONG_MANAGEABLE"
    REVERSIBLE = "REVERSIBLE"
    CURABLE = "CURABLE"
    SELF_LIMITING = "SELF_LIMITING"
    MAY_BE_OUTGROWN = "MAY_BE_OUTGROWN"


class PlanningMode(str, Enum):
    """How diet plans are generated for a condition"""
    AUTO_PLAN = "AUTO_PLAN"
    AUTO_PLAN_WITH_CLINICIAN_CONFIRMATION = "AUTO_PLAN_WITH_CLINICIAN_CONFIRMATION"
    CLINICIAN_ONLY_NO_AUTOPLAN = "CLINICIAN_ONLY_NO_AUTOPLAN"


class DataType(str, Enum):
    """Patient variable data types"""
    INTEGER = "INTEGER"
    REAL = "REAL"
    BOOLEAN = "BOOLEAN"
    STRING = "STRING"
    ENUM = "ENUM"


class SourceType(str, Enum):
    """Source of a patient variable"""
    LAB_REPORT = "LAB_REPORT"
    USER_ENTERED = "USER_ENTERED"
    CALCULATED = "CALCULATED"
