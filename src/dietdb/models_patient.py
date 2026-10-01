"""
Pydantic models - Part 3: Patient variables and conditions
"""

from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from dietdb.models import DataType, SourceType, Chronicity, PlanningMode


class PatientVariable(BaseModel):
    """Variable that rules may reference"""
    id: Optional[int] = None
    variable_name: str = Field(..., description="Machine-readable identifier")
    display_name: str
    data_type: DataType
    unit: Optional[str] = None
    allowed_values: Optional[list[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    source: SourceType
    description: Optional[str] = None


class Condition(BaseModel):
    """Medical condition/disease"""
    id: Optional[int] = None
    slug: str
    name: str
    icd10_code: Optional[str] = None
    category: str
    chronicity: Chronicity
    planning_mode: PlanningMode
    review_interval_months: int = 12
    eligibility_expression: Optional[dict] = None
    description: Optional[str] = None
    source_id: Optional[int] = None


class ConditionSynonym(BaseModel):
    """Alternative names for conditions"""
    id: Optional[int] = None
    condition_id: int
    synonym: str
    synonym_type: str = "ABBREVIATION"


class ConditionProfile(BaseModel):
    """Stage/variant of a condition"""
    id: Optional[int] = None
    condition_id: int
    slug: str
    name: str
    stage_or_variant: Optional[str] = None
    selector_expression: dict = Field(..., description="JSON expression tree")
    exclusivity_group: Optional[str] = None
    priority: int = 0
