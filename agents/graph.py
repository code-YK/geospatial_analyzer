"""
agents/graph.py — LangGraph StateGraph definition.

Wires all agent nodes together with conditional edges based on intent.
Uses Postgres-backed checkpointer for state persistence.
"""


from typing import Any

from langgraph.graph import END, StateGraph

from agents.state import AgentState
from agents.advisory import advisory_node
from agents.geospatial import geospatial_node
from agents.insight import insight_node
from agents.orchestrator import orchestrator_node
from core.database import get_session_factory
from core.logger import get_logger
from models.site import PrecomputedScores
from tools.config_tools import get_default_weights
from tools.explainability_tools import score_breakdown as compute_breakdown
from tools.scoring_tools import compute_final_score, rank_sites
from tools.site_tools import (
    fetch_precomputed_scores,
    fetch_site_features,
)

logger = get_logger(__name__)


# ── Intermediate Nodes ────────────────────────────────────────────────────

async def fetch_features_node(state: AgentState) -> dict:
    """Fetch all site features from DB for the primary site."""
    updates: dict = {"current_node": "fetch_features"}
    site_input = state.get("site_input")

    if site_input is None:
        updates["error"] = "No site input provided for feature fetch"
        return updates

    try:
        factory = get_session_factory()
        async with factory() as db:
            features = await fetch_site_features(
                lat=site_input.lat,
                lng=site_input.lng,
                h3_id=site_input.h3_id,
                db=db,
            )
            updates["site_features"] = features
    except Exception as exc:
        logger.error("fetch_features_node error: %s", exc)
        updates["error"] = f"Failed to fetch site features: {exc}"

    return updates


async def fetch_scores_node(state: AgentState) -> dict:
    """Fetch precomputed Layer 7 scores for the primary site."""
    updates: dict = {"current_node": "fetch_scores"}
    features = state.get("site_features")

    if features is None:
        updates["error"] = "No site features available for score fetch"
        return updates

    try:
        factory = get_session_factory()
        async with factory() as db:
            scores = await fetch_precomputed_scores(
                h3_id=features.grid_id,
                db=db,
            )
            updates["precomputed_scores"] = scores
    except Exception as exc:
        logger.error("fetch_scores_node error: %s", exc)
        updates["error"] = f"Failed to fetch precomputed scores: {exc}"

    return updates


async def compute_score_node(state: AgentState) -> dict:
    """Compute the final weighted site readiness score."""
    updates: dict = {"current_node": "compute_score"}

    precomputed = state.get("precomputed_scores")
    user_weights = state.get("user_weights")
    features = state.get("site_features")

    if precomputed is None:
        updates["error"] = "No precomputed scores available"
        return updates

    if user_weights is None:
        use_case = state.get("use_case", "retail")
        user_weights = get_default_weights(use_case)
        updates["user_weights"] = user_weights

    lat = features.latitude if features else 0.0
    lng = features.longitude if features else 0.0

    site_score = compute_final_score(
        precomputed_scores=precomputed,
        user_weights=user_weights,
        lat=lat,
        lng=lng,
    )

    updates["final_score"] = site_score.site_readiness_score

    # Handle comparison: score all comparison sites
    intent = state.get("intent", "")
    if intent == "compare_sites":
        comparison_sites = state.get("comparison_sites", [])
        all_scores = [site_score]

        if comparison_sites:
            factory = get_session_factory()
            async with factory() as db:
                for comp_site in comparison_sites:
                    try:
                        comp_features = await fetch_site_features(
                            lat=comp_site.lat,
                            lng=comp_site.lng,
                            h3_id=comp_site.h3_id,
                            db=db,
                        )
                        comp_precomputed = await fetch_precomputed_scores(
                            h3_id=comp_features.grid_id,
                            db=db,
                        )
                        comp_score = compute_final_score(
                            precomputed_scores=comp_precomputed,
                            user_weights=user_weights,
                            lat=comp_features.latitude,
                            lng=comp_features.longitude,
                        )
                        all_scores.append(comp_score)
                    except Exception as exc:
                        logger.warning("Failed to score comparison site: %s", exc)

        updates["comparison_results"] = rank_sites(all_scores)

    return updates


async def explainability_node(state: AgentState) -> dict:
    """Generate the score breakdown with strengths/weaknesses."""
    updates: dict = {"current_node": "explainability"}

    precomputed = state.get("precomputed_scores")
    user_weights = state.get("user_weights")
    features = state.get("site_features")

    if precomputed is None or user_weights is None:
        updates["error"] = "Missing data for explainability"
        return updates

    lat = features.latitude if features else 0.0
    lng = features.longitude if features else 0.0

    site_score = compute_final_score(
        precomputed_scores=precomputed,
        user_weights=user_weights,
        lat=lat,
        lng=lng,
    )

    breakdown = compute_breakdown(site_score)
    updates["score_breakdown"] = breakdown

    return updates


async def error_handler_node(state: AgentState) -> dict:
    """Format errors gracefully."""
    error = state.get("error", "An unknown error occurred")
    return {
        "current_node": "error_handler",
        "insight_text": f"⚠ Error: {error}",
    }


# ── Routing Function ─────────────────────────────────────────────────────

def route_after_orchestrator(state: AgentState) -> str:
    """Conditional routing based on detected intent."""
    intent = state.get("intent", "error")
    error = state.get("error")

    if error:
        return "error_handler"

    routing = {
        "advise_weights": "advisory",
        "score_site": "fetch_features",
        "compare_sites": "fetch_features",
        "find_hotspots": "geospatial",
        "explain_result": "fetch_features",
    }

    return routing.get(intent, "error_handler")


# ── Graph Builder ─────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Build and compile the LangGraph StateGraph.

    Node layout:
        START → orchestrator → [conditional routing]
            ├─ advise_weights  → advisory → fetch_features → fetch_scores → compute_score → explainability → insight → END
            ├─ score_site      → fetch_features → fetch_scores → compute_score → explainability → insight → END
            ├─ compare_sites   → fetch_features → fetch_scores → compute_score → explainability → insight → END
            ├─ find_hotspots   → geospatial → insight → END
            ├─ explain_result  → fetch_features → fetch_scores → explainability → insight → END
            └─ error           → error_handler → END
    """
    graph = StateGraph(AgentState)

    # ── Add nodes ────────────────────────────────────────────────────
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("advisory", advisory_node)
    graph.add_node("fetch_features", fetch_features_node)
    graph.add_node("fetch_scores", fetch_scores_node)
    graph.add_node("compute_score", compute_score_node)
    graph.add_node("geospatial", geospatial_node)
    graph.add_node("explainability", explainability_node)
    graph.add_node("insight", insight_node)
    graph.add_node("error_handler", error_handler_node)

    # ── Entry point ──────────────────────────────────────────────────
    graph.set_entry_point("orchestrator")

    # ── Conditional edges from orchestrator ──────────────────────────
    graph.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {
            "advisory": "advisory",
            "fetch_features": "fetch_features",
            "geospatial": "geospatial",
            "error_handler": "error_handler",
        },
    )

    # ── Linear edges ─────────────────────────────────────────────────
    graph.add_edge("advisory", "fetch_features")
    graph.add_edge("fetch_features", "fetch_scores")
    graph.add_edge("fetch_scores", "compute_score")
    graph.add_edge("compute_score", "explainability")
    graph.add_edge("explainability", "insight")
    graph.add_edge("geospatial", "insight")
    graph.add_edge("insight", END)
    graph.add_edge("error_handler", END)

    return graph


def get_compiled_graph(checkpointer: Any = None):
    """
    Compile the graph with an optional checkpointer.

    Parameters
    ----------
    checkpointer : optional
        A LangGraph checkpointer (e.g. PostgresSaver) for state persistence.
    """
    graph = build_graph()
    return graph.compile(checkpointer=checkpointer)


# ── Module-level compiled graph (for LangGraph Studio / CLI) ─────────────
# langgraph.json references this as: ./agents/graph.py:graph
graph = get_compiled_graph()
