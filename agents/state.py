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
    use_case: str  # "retail" | "ev_charging" | "warehouse" | ... (any key in USE_CASE_CATALOG)
    site_input: SiteInput
    user_weights: Optional[WeightConfig]
    comparison_sites: Optional[List[SiteInput]]
    request_explanation: bool  # set True by CLI to trigger explain_result flow

    # ── Routing / flow control ────────────────────────────────────────
    intent: str  # "score_site" | "compare_sites" | "find_hotspots" | "explain_result" | "advise_weights"
    current_node: str
    error: Optional[str]
    state_name: str  # populated by CLI for find_hotspots flow

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

    # ── Chat layer ────────────────────────────────────────────────────
    conversation_history: List[dict]     # [{"role": "user"/"assistant", "content": "..."}]
    chat_intent: str                     # "needs_graph" | "direct_answer" | "follow_up" | "off_topic"
    missing_fields: List[str]            # e.g. ["lat", "lng"] — what chat node still needs
    retry_count: int                     # increments on each off-topic / invalid attempt
    analysis_complete: bool              # True after graph has run once in this session
    raw_user_message: str                # original unprocessed user input
    chat_response: str                   # chat node's reply to user (not insight_text)

    # ── Validation ────────────────────────────────────────────────────
    validation_warnings: List[str]       # regulatory warnings from validation node

