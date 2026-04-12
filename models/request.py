"""
models/request.py — API request/response models for FastAPI routes.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from models.site import (
    HotspotResult,
    ScoreBreakdown,
    SiteInput,
    SiteScore,
    WhatIfResult,
)
from models.weights import WeightConfig


# ── Request Bodies ────────────────────────────────────────────────────────

class ScoreRequest(BaseModel):
    """POST /score request body."""

    site_input: SiteInput
    use_case: str = Field(
        ...,
        pattern="^(retail|ev_charging|warehouse|telecom|renewable)$",
        description="Business use case",
    )
    weights: Optional[WeightConfig] = None


class WhatIfRequest(BaseModel):
    """POST /score/what-if request body."""

    site_id: str
    current_weights: WeightConfig
    modified_weights: WeightConfig


class CompareRequest(BaseModel):
    """POST /compare request body."""

    sites: List[SiteInput] = Field(..., min_length=2, max_length=5)
    use_case: str = Field(
        ...,
        pattern="^(retail|ev_charging|warehouse|telecom|renewable)$",
    )
    weights: Optional[WeightConfig] = None


class HotspotRequest(BaseModel):
    """POST /hotspots request body."""

    state: str
    use_case: str = Field(
        ...,
        pattern="^(retail|ev_charging|warehouse|telecom|renewable)$",
    )
    weights: Optional[WeightConfig] = None
    top_n: int = Field(10, ge=1, le=100)


# ── Response Bodies ───────────────────────────────────────────────────────

class ScoreResponse(BaseModel):
    """POST /score response."""

    site_score: SiteScore
    score_breakdown: ScoreBreakdown
    insight_text: str
    advisory_text: Optional[str] = None


class CompareResponse(BaseModel):
    """POST /compare response."""

    ranked_sites: List[SiteScore]
    insight_text: str


class HotspotResponse(BaseModel):
    """POST /hotspots response."""

    hotspots: List[HotspotResult]
    insight_text: str


class WhatIfResponse(BaseModel):
    """POST /score/what-if response."""

    result: WhatIfResult


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    error_type: str = "GeoAnalyzerError"


# ── Checkpoint Endpoint Models ─────────────────────────────────────────────

class CheckpointScoreRequest(BaseModel):
    """Request body for POST /checkpoint/score."""

    site_input: SiteInput
    use_case: str = Field(
        ...,
        description="Business use case key e.g. 'retail', 'ev_charging'",
    )
    weights: Optional[WeightConfig] = Field(
        default=None,
        description=(
            "Optional scoring weights. If omitted, advisory node recommends defaults."
        ),
    )

    @field_validator("use_case")
    @classmethod
    def use_case_must_be_valid(cls, v: str) -> str:
        from scoring.weights import VALID_USE_CASES

        if v not in VALID_USE_CASES:
            raise ValueError(
                f"Invalid use_case '{v}'. "
                f"Valid options: {sorted(VALID_USE_CASES)}"
            )
        return v


class CheckpointScoreResponse(BaseModel):
    """Response body for POST /checkpoint/score."""

    site_id: Optional[str] = None
    location: str
    use_case: str
    final_score: Optional[float] = None
    score_breakdown: Optional[ScoreBreakdown] = None
    weights_used: Optional[WeightConfig] = None
    insight_text: Optional[str] = None
    advisory_text: Optional[str] = None
    validation_warnings: List[str] = Field(default_factory=list)
    thread_id: str

