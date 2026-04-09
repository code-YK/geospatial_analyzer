"""
models/weights.py — WeightConfig Pydantic model.

Defines the 6-dimension weight schema used across scoring, advisory, and CLI.
"""

from pydantic import BaseModel, Field, model_validator


class WeightConfig(BaseModel):
    """
    Six scoring weights that must sum to 1.0 (±0.01 tolerance).

    Each weight is in [0.0, 1.0] and represents the relative importance
    of a scoring dimension in the site readiness calculation.
    """

    demand_score: float = Field(..., ge=0.0, le=1.0, description="Weight for demand score")
    accessibility_score: float = Field(..., ge=0.0, le=1.0, description="Weight for accessibility score")
    competition_score: float = Field(..., ge=0.0, le=1.0, description="Weight for competition score")
    suitability_score: float = Field(..., ge=0.0, le=1.0, description="Weight for suitability score")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Weight for risk score")
    infrastructure_score: float = Field(..., ge=0.0, le=1.0, description="Weight for infrastructure score")

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "WeightConfig":
        total = sum([
            self.demand_score,
            self.accessibility_score,
            self.competition_score,
            self.suitability_score,
            self.risk_score,
            self.infrastructure_score,
        ])
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {total:.3f}")
        return self
