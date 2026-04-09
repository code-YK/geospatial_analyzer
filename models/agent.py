"""
models/agent.py — Agent input/output models for the LangGraph pipeline.
"""

from typing import List, Optional

from pydantic import BaseModel

from models.site import (
    HotspotResult,
    ScoreBreakdown,
    SiteInput,
    SiteScore,
)
from models.weights import WeightConfig


class AgentInput(BaseModel):
    """Input payload to kick off the LangGraph agent graph."""

    thread_id: str
    use_case: str
    site_input: SiteInput
    user_weights: Optional[WeightConfig] = None
    comparison_sites: Optional[List[SiteInput]] = None


class AgentOutput(BaseModel):
    """Final output from the LangGraph agent graph."""

    site_score: Optional[SiteScore] = None
    score_breakdown: Optional[ScoreBreakdown] = None
    comparison_results: Optional[List[SiteScore]] = None
    hotspot_results: Optional[List[HotspotResult]] = None
    insight_text: str = ""
    advisory_text: Optional[str] = None
    recommended_weights: Optional[WeightConfig] = None
    error: Optional[str] = None
