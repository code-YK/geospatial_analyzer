"""
agents/geospatial.py — Geo-Spatial Agent node.

Handles hotspot detection and catchment analysis.
Does NOT call LLM — purely tool execution.
"""

from agents.state import AgentState
from core.database import get_session_factory
from core.logger import get_logger
from tools.config_tools import get_default_weights
from tools.spatial_tools import catchment_analysis, detect_hotspots

logger = get_logger(__name__)


async def geospatial_node(state: AgentState) -> dict:
    """
    Geospatial node — handles ``find_hotspots`` and catchment intents.

    Calls spatial_tools and populates the state with results.
    Does NOT call LLM.
    """
    updates: dict = {"current_node": "geospatial"}
    intent = state.get("intent", "")
    use_case = state.get("use_case", "retail")

    # Resolve weights
    user_weights = state.get("user_weights")
    if user_weights is None:
        user_weights = get_default_weights(use_case)

    factory = get_session_factory()

    try:
        async with factory() as db:
            if intent == "find_hotspots":
                # Extract state from site_input or use a default
                site_input = state.get("site_input")
                state_name = ""
                if site_input and hasattr(site_input, "h3_id") and site_input.h3_id:
                    # Try to get state from features if available
                    features = state.get("site_features")
                    if features:
                        state_name = features.state
                if not state_name:
                    # The CLI / API should have set this somewhere;
                    # we'll check site_features or default
                    features = state.get("site_features")
                    state_name = features.state if features else "Gujarat"

                results = await detect_hotspots(
                    state=state_name,
                    use_case=use_case,
                    user_weights=user_weights,
                    top_n=10,
                    db=db,
                )
                updates["hotspot_results"] = results

            else:
                logger.warning("Geospatial node called with unknown intent: %s", intent)

    except Exception as exc:
        logger.error("Geospatial node error: %s", exc)
        updates["error"] = f"Geospatial analysis failed: {exc}"

    return updates
