"""
agents/insight.py — LLM insight generator node.

The ONLY place where LLM is used to generate user-facing natural language
from structured scoring results.
"""


from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import AgentState
from core.logger import get_logger
from llm.llm_config import get_llm
from llm.prompts import (
    INSIGHT_COMPARISON_USER_PROMPT,
    INSIGHT_HOTSPOT_USER_PROMPT,
    INSIGHT_SCORE_USER_PROMPT,
    INSIGHT_SYSTEM_PROMPT,
)

logger = get_logger(__name__)


async def insight_node(state: AgentState) -> dict:
    """
    Insight node — converts structured results into natural language.

    Only passes the 8–10 most relevant fields to the LLM (never the
    full 71-column SiteFeatures).
    """
    updates: dict = {"current_node": "insight"}
    intent = state.get("intent", "")

    try:
        llm = get_llm()

        user_prompt = _build_user_prompt(state, intent)
        logger.info("Insight LLM call started for intent=%s", intent)

        messages = [
            SystemMessage(content=INSIGHT_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        response = await llm.ainvoke(messages)
        updates["insight_text"] = response.content.strip()
        logger.info(
            "Insight generated: %d chars for intent=%s",
            len(updates["insight_text"]), intent,
        )

    except Exception as exc:
        logger.error("Insight LLM call failed: %s", exc)
        updates["insight_text"] = _build_fallback_insight(state, intent)

    return updates


def _build_user_prompt(state: AgentState, intent: str) -> str:
    """Build the user prompt based on the current intent and state data."""

    if intent in ("score_site", "advise_weights"):
        features = state.get("site_features")
        breakdown = state.get("score_breakdown")
        final_score = state.get("final_score", 0.0)

        # Format score breakdown for prompt
        breakdown_text = ""
        if breakdown:
            for dim, contrib in breakdown.contributions.items():
                breakdown_text += (
                    f"  {dim}: raw={contrib.raw:.0f}, "
                    f"weight={contrib.weight:.2f}, "
                    f"contribution={contrib.contribution:.1f} "
                    f"(rank #{contrib.rank})\n"
                )

        return INSIGHT_SCORE_USER_PROMPT.format(
            use_case=state.get("use_case", ""),
            state=getattr(features, "state", "N/A") if features else "N/A",
            district=getattr(features, "district", "N/A") if features else "N/A",
            area_name=getattr(features, "area_name", "N/A") if features else "N/A",
            grid_id=getattr(features, "grid_id", "N/A") if features else "N/A",
            lat=getattr(features, "latitude", 0) if features else 0,
            lng=getattr(features, "longitude", 0) if features else 0,
            population_density=getattr(features, "population_density", "N/A") if features else "N/A",
            score_breakdown=breakdown_text or "N/A",
            site_readiness_score=final_score or 0.0,
            strengths=", ".join(breakdown.strengths) if breakdown else "N/A",
            weaknesses=", ".join(breakdown.weaknesses) if breakdown else "N/A",
        )

    elif intent == "explain_result":
        features = state.get("site_features")
        breakdown = state.get("score_breakdown")
        final_score = state.get("final_score", 0.0)
        breakdown_text = ""
        if breakdown:
            for dim, contrib in breakdown.contributions.items():
                breakdown_text += (
                    f"  {dim}: raw={contrib.raw:.0f}, "
                    f"weight={contrib.weight:.2f}, "
                    f"contribution={contrib.contribution:.1f} "
                    f"(rank #{contrib.rank})\n"
                )
        return INSIGHT_SCORE_USER_PROMPT.format(
            use_case=state.get("use_case", ""),
            state=getattr(features, "state", "N/A") if features else "N/A",
            district=getattr(features, "district", "N/A") if features else "N/A",
            area_name=getattr(features, "area_name", "N/A") if features else "N/A",
            grid_id=getattr(features, "grid_id", "N/A") if features else "N/A",
            lat=getattr(features, "latitude", 0) if features else 0,
            lng=getattr(features, "longitude", 0) if features else 0,
            population_density=getattr(features, "population_density", "N/A") if features else "N/A",
            score_breakdown=breakdown_text or "N/A",
            site_readiness_score=final_score,
            strengths=", ".join(breakdown.strengths) if breakdown else "N/A",
            weaknesses=", ".join(breakdown.weaknesses) if breakdown else "N/A",
        )

    elif intent == "compare_sites":
        comparison = state.get("comparison_results", [])
        table_lines = []
        for i, site in enumerate(comparison or [], 1):
            table_lines.append(
                f"  #{i} Grid {site.grid_id}: "
                f"score={site.site_readiness_score:.1f}"
            )

        return INSIGHT_COMPARISON_USER_PROMPT.format(
            use_case=state.get("use_case", ""),
            num_sites=len(comparison or []),
            comparison_table="\n".join(table_lines) or "N/A",
        )

    elif intent == "find_hotspots":
        hotspots = state.get("hotspot_results", [])
        table_lines = []
        for i, hs in enumerate(hotspots or [], 1):
            table_lines.append(
                f"  #{i} {hs.district}, {hs.state} "
                f"(Grid {hs.grid_id}): score={hs.site_readiness_score:.1f}"
            )

        state_label = state.get("state_name") or "India"
        return INSIGHT_HOTSPOT_USER_PROMPT.format(
            use_case=state.get("use_case", ""),
            state=state_label,
            top_n=len(hotspots or []),
            hotspot_table="\n".join(table_lines) or "N/A",
        )

    return f"Intent: {intent}\nPlease provide a general insight based on the analysis."


def _build_fallback_insight(state: AgentState, intent: str) -> str:
    """Build a fallback text insight when the LLM is unavailable."""
    final_score = state.get("final_score", 0)
    use_case = state.get("use_case", "general")

    if intent in ("score_site", "advise_weights", "explain_result"):
        return (
            f"Site readiness score: {final_score:.1f}/100 for {use_case}. "
            f"(Detailed LLM insight unavailable — see score breakdown above.)"
        )
    elif intent == "compare_sites":
        return "Site comparison complete (detailed LLM insight unavailable)."
    elif intent == "find_hotspots":
        return "Hotspot detection complete (detailed LLM insight unavailable)."
    return "Analysis complete."
