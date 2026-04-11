"""
agents/graph.py — LangGraph StateGraph definition.

Wires all agent nodes together with conditional edges based on intent.
Uses Postgres-backed checkpointer for state persistence.

v2: Chat node as START, validation node before scoring,
    chat_response node after insight.
"""


from typing import Any

from langgraph.graph import END, StateGraph

from agents.state import AgentState
from agents.advisory import advisory_node
from agents.chat import chat_node, chat_response_node
from agents.geospatial import geospatial_node
from agents.insight import insight_node
from agents.orchestrator import orchestrator_node
from core.config import get_settings
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
from tools.validation_tools import run_all_validations

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
                site_id=features.id,
                db=db,
            )
            updates["precomputed_scores"] = scores
    except Exception as exc:
        logger.error("fetch_scores_node error: %s", exc)
        updates["error"] = f"Failed to fetch precomputed scores: {exc}"

    return updates


async def validation_node(state: AgentState) -> dict:
    """
    Runs AFTER fetch_scores, BEFORE compute_score.

    - Calls run_all_validations()
    - If any result is "block": set state["error"], route to error_handler
    - If warns: apply score penalties to precomputed_scores,
                collect messages into state["validation_warnings"]
    """
    updates: dict = {"current_node": "validation"}

    use_case = state.get("use_case", "retail")
    state_name = state.get("state_name", "")
    site_features = state.get("site_features")
    precomputed = state.get("precomputed_scores")

    if site_features is None:
        # Nothing to validate — let downstream nodes handle
        return updates

    # Infer state_name from features if not provided
    if not state_name and hasattr(site_features, "state"):
        state_name = getattr(site_features, "state", "")
        updates["state_name"] = state_name

    results = run_all_validations(use_case, state_name, site_features)

    blocks = [r for r in results if r.status == "block"]
    warns = [r for r in results if r.status == "warn"]

    if blocks:
        block = blocks[0]
        updates["error"] = (
            f"⛔ This location is not suitable for "
            f"**{use_case.replace('_', ' ')}**.\n\n"
            f"**Reason:** {block.reason}\n"
            f"**Regulation:** {block.regulation_ref or 'N/A'}"
        )
        return updates

    if warns and precomputed is not None:
        # Apply penalties to a copy of precomputed scores
        score_dict = precomputed.model_dump()
        for w in warns:
            if w.penalty_dimension and w.penalty_points > 0:
                dim = w.penalty_dimension
                if dim in score_dict:
                    score_dict[dim] = max(0.0, score_dict[dim] - w.penalty_points)
                    logger.info(
                        "Validation penalty: %s −%.0f on %s",
                        w.reason[:60], w.penalty_points, dim,
                    )

        updates["precomputed_scores"] = PrecomputedScores(**score_dict)
        updates["validation_warnings"] = [w.reason for w in warns]

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
        failed_count = 0

        if comparison_sites:
            factory = get_session_factory()
            async with factory() as db:
                for comp_site in comparison_sites:
                    try:
                        comp_features = await fetch_site_features(
                            lat=comp_site.lat,
                            lng=comp_site.lng,
                            db=db,
                        )
                        comp_precomputed = await fetch_precomputed_scores(
                            site_id=comp_features.id,
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
                        logger.warning("Failed to score comparison site %s: %s", comp_site, exc)
                        failed_count += 1

        updates["comparison_results"] = rank_sites(all_scores)

        if failed_count:
            updates["error"] = (
                f"Warning: {failed_count} of {len(comparison_sites)} comparison "
                f"site(s) could not be scored and were excluded from results."
            )

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
    updates["final_score"] = site_score.site_readiness_score

    return updates


async def error_handler_node(state: AgentState) -> dict:
    """Format errors gracefully."""
    error = state.get("error", "An unknown error occurred")
    return {
        "current_node": "error_handler",
        "insight_text": f"⚠ Error: {error}",
        "chat_response": f"⚠ {error}",
    }


# ── Routing Functions ────────────────────────────────────────────────────

def route_after_chat(state: AgentState) -> str:
    """Route after chat_node based on chat_intent."""
    intent = state.get("chat_intent", "")
    error = state.get("error")

    if error:
        return "error_handler"

    routing = {
        "needs_graph":    "orchestrator",
        "direct_answer":  "__end__",
        "follow_up":      "__end__",
        "ask_field":      "__end__",
        "off_topic":      "__end__",
    }

    return routing.get(intent, "__end__")


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


def route_after_fetch_features(state: AgentState) -> str:
    return "error_handler" if state.get("error") else "fetch_scores"


def route_after_fetch_scores(state: AgentState) -> str:
    return "error_handler" if state.get("error") else "validation"


def route_after_validation(state: AgentState) -> str:
    return "error_handler" if state.get("error") else "compute_score"


def route_after_compute_score(state: AgentState) -> str:
    return "error_handler" if state.get("error") else "explainability"


def route_after_explainability(state: AgentState) -> str:
    return "error_handler" if state.get("error") else "insight"


# ── Graph Builder ─────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Build and compile the LangGraph StateGraph.

    Node layout (v2 — chat-first with validation):

        START → chat_node → [conditional on chat_intent]
            ├── needs_graph → orchestrator → [conditional on intent]
            │       ├── advise_weights → advisory → fetch_features → fetch_scores → validation → compute_score → explainability → insight → chat_response → END
            │       ├── score_site     → fetch_features → ... → chat_response → END
            │       ├── compare_sites  → fetch_features → ... → chat_response → END
            │       ├── explain_result → fetch_features → ... → chat_response → END
            │       ├── find_hotspots  → geospatial → insight → chat_response → END
            │       └── error          → error_handler → END
            ├── direct_answer / follow_up / ask_field → END (chat_response set)
            └── off_topic (retry exceeded) → error_handler → END
    """
    graph = StateGraph(AgentState)

    # ── Add nodes ────────────────────────────────────────────────────
    graph.add_node("chat", chat_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("advisory", advisory_node)
    graph.add_node("fetch_features", fetch_features_node)
    graph.add_node("fetch_scores", fetch_scores_node)
    graph.add_node("validation", validation_node)
    graph.add_node("compute_score", compute_score_node)
    graph.add_node("geospatial", geospatial_node)
    graph.add_node("explainability", explainability_node)
    graph.add_node("insight", insight_node)
    graph.add_node("chat_response", chat_response_node)
    graph.add_node("error_handler", error_handler_node)

    # ── Entry point ──────────────────────────────────────────────────
    graph.set_entry_point("chat")

    # ── Conditional edges from chat_node ─────────────────────────────
    graph.add_conditional_edges(
        "chat",
        route_after_chat,
        {
            "orchestrator": "orchestrator",
            "error_handler": "error_handler",
            "__end__": END,
        },
    )

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

    # ── Linear edges (no error possible) ─────────────────────────────
    graph.add_edge("advisory", "fetch_features")
    graph.add_edge("geospatial", "insight")
    graph.add_edge("insight", "chat_response")
    graph.add_edge("chat_response", END)
    graph.add_edge("error_handler", END)

    # ── Conditional edges (error → error_handler) ────────────────────
    graph.add_conditional_edges("fetch_features", route_after_fetch_features,
        {"fetch_scores": "fetch_scores", "error_handler": "error_handler"})
    graph.add_conditional_edges("fetch_scores", route_after_fetch_scores,
        {"validation": "validation", "error_handler": "error_handler"})
    graph.add_conditional_edges("validation", route_after_validation,
        {"compute_score": "compute_score", "error_handler": "error_handler"})
    graph.add_conditional_edges("compute_score", route_after_compute_score,
        {"explainability": "explainability", "error_handler": "error_handler"})
    graph.add_conditional_edges("explainability", route_after_explainability,
        {"insight": "insight", "error_handler": "error_handler"})

    return graph


def get_compiled_graph(checkpointer: Any = None):
    """
    Compile the graph with an optional checkpointer.

    Parameters
    ----------
    checkpointer : optional
        A LangGraph checkpointer (e.g. AsyncPostgresSaver) for state persistence.
    """
    graph = build_graph()
    return graph.compile(checkpointer=checkpointer)


async def create_checkpointer():
    """
    Create and set up an AsyncPostgresSaver using langgraph_checkpoint_url.
    Must be called once at application startup before the graph is invoked.
    Returns a ready-to-use checkpointer for passing to get_compiled_graph().
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    settings = get_settings()
    checkpointer = AsyncPostgresSaver.from_conn_string(
        settings.langgraph_checkpoint_url
    )
    await checkpointer.setup()
    logger.info("LangGraph AsyncPostgresSaver checkpointer ready")
    return checkpointer


# ── Module-level compiled graph (for LangGraph Studio / CLI) ─────────────
# NOTE: This module-level export uses NO checkpointer — it is for LangGraph Studio
# graph visualization only. For runtime use, call create_checkpointer() at startup
# and pass the result to get_compiled_graph(checkpointer=cp).
graph = get_compiled_graph()
