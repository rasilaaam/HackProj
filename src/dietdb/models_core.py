"""
Pydantic models - Part 2: Core data models
"""

from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from dietdb.models import (
    ValueStatus, FoodState, NutrientCategory, AllergenPresence,
    RuleKind, RuleTargetType, RuleBasis, RuleTier, RuleEnforcement,
    RuleStatus, Chronicity, PlanningMode, DataType, SourceType
)


# ============================================================
# SOURCE & NUTRIENT MODELS
# ============================================================

class Source(BaseModel):
    """Data source attribution"""
    id: Optional[int] = None
    slug: str
    name: str
    description: Optional[str] = None
    version: Optional[str] = None
    year: Optional[int] = None
    publisher: Optional[str] = None
    license: Optional[str] = None
    attribution: Optional[str] = None
    source_url: Optional[str] = None
    local_path: Optional[str] = None
    checksum: Optional[str] = None
    verification_status: str = "UNVERIFIED"
    notes: Optional[str] = None


class Nutrient(BaseModel):
    """Nutrient definition"""
    id: Optional[int] = None
    canonical_name: str = Field(..., description="Machine-readable identifier")
    display_name: str
    category: NutrientCategory
    canonical_unit: str = Field(..., description="SI/canonical unit")
    ifct_column_code: Optional[str] = None
    parent_id: Optional[int] = None
    is_constrainable: bool = False
    conversion_factor: Optional[float] = None
    native_unit: Optional[str] = None
    sort_order: int = 0


class FoodGroup(BaseModel):
    """Classification of foods"""
    id: Optional[int] = None
    code: str
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    level: int = 0


# ============================================================
# FOOD MODELS
# ============================================================

class Food(BaseModel):
    """Food item"""
    id: Optional[int] = None
    source_code: str
    source_id: int
    english_name: str
    scientific_name: Optional[str] = None
    food_group_id: Optional[int] = None
    edible_portion_pct: Optional[float] = None
    food_state: FoodState = FoodState.RAW
    reference_basis: str = "PER_100G_EDIBLE"
    notes: Optional[str] = None
    quality_flag: Optional[str] = None


class FoodAlias(BaseModel):
    """Multilingual food name variants"""
    id: Optional[int] = None
    food_id: int
    alias: str
    language: str = Field(..., description="Language code: en, hi, ta, te, etc.")
    script: str = "Latn"
    alias_type: str = "COMMON"
    is_preferred: bool = False


class FoodNutrient(BaseModel):
    """Nutrient value for a food"""
    food_id: int
    nutrient_id: int
    value_native: Optional[float] = None
    unit_native: str
    value_canonical: Optional[float] = None
    canonical_unit: str
    sd: Optional[float] = None
    value_status: ValueStatus
    raw_text: Optional[str] = None
    source_id: int
    source_row: Optional[int] = None

    @field_validator("value_canonical", mode="before")
    @classmethod
    def validate_canonical_value(cls, v: Any, info: Any) -> Optional[float]:
        """Ensure canonical values are non-negative unless NOT_DETECTED or NOT_ANALYSED"""
        if v is None:
            return None
        if v < 0:
            status = info.data.get("value_status")
            if status not in [ValueStatus.NOT_DETECTED, ValueStatus.NOT_ANALYSED]:
                raise ValueError(f"Negative value {v} not allowed for status {status}")
        return v
