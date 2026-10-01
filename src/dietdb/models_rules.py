"""
Pydantic models - Part 4: Diet rules
"""

from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from dietdb.models import (
    RuleKind, RuleTargetType, RuleBasis, RuleTier, RuleEnforcement, RuleStatus
)


class Rule(BaseModel):
    """Diet rule - NO DEFAULT RULES FROM MEMORY, TEST FIXTURES ONLY"""
    id: Optional[int] = None
    slug: str
    name: str
    kind: RuleKind
    target_type: RuleTargetType
    target_ref: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    target_value: Optional[float] = None
    tolerance: Optional[float] = None
    unit: Optional[str] = None
    basis: RuleBasis
    tier: RuleTier
    enforcement: RuleEnforcement
    applies_when: dict = Field(..., description="JSON expression tree")
    rationale: str = Field(..., description="Patient-facing explanation")
    source_id: Optional[int] = None
    source_locator: Optional[str] = None
    evidence_grade: Optional[str] = None
    status: RuleStatus
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    version: int = 1
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None

    @field_validator("applies_when", mode="before")
    @classmethod
    def parse_applies_when(cls, v: Any) -> dict:
        """Ensure applies_when is a valid dict"""
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "slug": "t2dm_protein_bound_test",
                    "name": "Type 2 Diabetes - Protein Bound (TEST FIXTURE)",
                    "kind": "NUTRIENT_BOUND",
                    "target_type": "NUTRIENT",
                    "target_ref": "protein",
                    "min_value": 50,
                    "max_value": 100,
                    "unit": "g",
                    "basis": "PER_DAY",
                    "tier": "THERAPEUTIC",
                    "enforcement": "HARD",
                    "applies_when": {"op": "and", "conditions": [{"field": "has_t2dm", "op": "eq", "value": True}]},
                    "rationale": "Moderate protein intake is therapeutic for type 2 diabetes",
                    "status": "DRAFT"
                }
            ]
        }


class RuleProfile(BaseModel):
    """Links rules to condition profiles"""
    rule_id: int
    condition_profile_id: int
