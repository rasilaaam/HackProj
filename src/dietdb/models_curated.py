"""
Pydantic models - Part 5: Curated food data and quality
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from dietdb.models import AllergenPresence


class Allergen(BaseModel):
    """Allergen definition"""
    id: Optional[int] = None
    code: str
    name: str
    description: Optional[str] = None


class FoodTag(BaseModel):
    """Allergen presence/absence for a food"""
    id: Optional[int] = None
    food_id: int
    allergen_id: int
    presence: AllergenPresence = AllergenPresence.UNKNOWN
    source_id: Optional[int] = None
    assessed_at: Optional[datetime] = None
    notes: Optional[str] = None


class DietType(BaseModel):
    """Diet pattern classification"""
    id: Optional[int] = None
    code: str
    name: str
    description: Optional[str] = None


class DietTypeTag(BaseModel):
    """Food compatibility with diet pattern"""
    id: Optional[int] = None
    food_id: int
    diet_type_id: int
    is_compatible: bool = True
    source_id: Optional[int] = None


class PurineLevel(BaseModel):
    """Purine content classification"""
    id: Optional[int] = None
    level: str
    description: Optional[str] = None
    mg_per_100g_min: Optional[float] = None
    mg_per_100g_max: Optional[float] = None


class FoodPurineLevel(BaseModel):
    """Purine content for a food"""
    food_id: int
    purine_level_id: int
    mg_per_100g: Optional[float] = None
    source_id: Optional[int] = None


class GlycemicIndex(BaseModel):
    """Glycemic Index/Load data"""
    food_id: int
    gi_value: Optional[int] = Field(None, ge=0, le=100)
    gl_basis_serving: Optional[float] = None
    gl_basis_reference: float = 50
    method: Optional[str] = None
    source_id: Optional[int] = None
    measured_at: Optional[datetime] = None


class HouseholdMeasure(BaseModel):
    """Indian portion measures"""
    id: Optional[int] = None
    food_id: int
    measure_type: str = Field(..., description="KATORI, ROTI, GLASS, TSP, TBSP, PIECE, HANDFUL")
    grams: float = Field(..., gt=0)
    volume_ml: Optional[float] = None
    description: Optional[str] = None
    source_id: Optional[int] = None


class Price(BaseModel):
    """Food price data"""
    id: Optional[int] = None
    food_id: int
    price_inr_per_kg: float = Field(..., gt=0)
    region: str
    as_of_date: str
    source_id: Optional[int] = None


class Preparation(BaseModel):
    """Cooking method"""
    id: Optional[int] = None
    food_id: int
    method: str
    weight_yield_factor: Optional[float] = None
    description: Optional[str] = None
    source_id: Optional[int] = None


class PreparationEffect(BaseModel):
    """Nutrient retention during cooking"""
    id: Optional[int] = None
    preparation_id: int
    nutrient_id: int
    retention_factor: float = Field(..., ge=0, le=1)
    source_id: Optional[int] = None


class DataQualityFlag(BaseModel):
    """Data quality issue"""
    id: Optional[int] = None
    table_name: str
    record_id: int
    flag_type: str
    severity: str = Field("WARNING", pattern="^(INFO|WARNING|ERROR)$")
    description: str
    field_name: Optional[str] = None
    raw_value: Optional[str] = None
    expected_value: Optional[str] = None
    resolved: bool = False
    resolution_notes: Optional[str] = None
    flagged_by: str = "SYSTEM"
