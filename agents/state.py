"""
agents/state.py — AgentState TypedDict for the LangGraph state graph.
"""

from typing import List, Optional, TypedDict

from models.site import (
    HotspotResult,
    PrecomputedScores,
    ScoreBreakdown,
    SiteFeatures,
    SiteInput,
    SiteScore,
)
from models.weights import WeightConfig


class AgentState(TypedDict, total=False):
    """
    Shared state flowing through the LangGraph state graph.

    All keys are optional (total=False) because different nodes
    populate different subsets of the state.
    """

    # ── Input ─────────────────────────────────────────────────────────
    thread_id: str
    use_case: str  # "retail" | "ev_charging" | "warehouse" | "telecom" | "renewable"
    site_input: SiteInput
    user_weights: Optional[WeightConfig]
    comparison_sites: Optional[List[SiteInput]]

    # ── Routing / flow control ────────────────────────────────────────
    intent: str  # "score_site" | "compare_sites" | "find_hotspots" | "explain_result" | "advise_weights"
    current_node: str
    error: Optional[str]

    # ── Data payloads (populated by tools as graph progresses) ────────
    site_features: Optional[SiteFeatures]
    precomputed_scores: Optional[PrecomputedScores]
    final_score: Optional[float]
    score_breakdown: Optional[ScoreBreakdown]
    comparison_results: Optional[List[SiteScore]]
    hotspot_results: Optional[List[HotspotResult]]

    # ── Output ────────────────────────────────────────────────────────
    insight_text: str
    advisory_text: Optional[str]
    recommended_weights: Optional[WeightConfig]
