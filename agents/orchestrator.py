"""
agents/orchestrator.py — Deterministic routing node.

No LLM call. Validates input and detects intent purely from
the request structure.
"""

from agents.state import AgentState
from core.exceptions import InvalidCoordinatesError
from core.logger import get_logger
from tools.config_tools import validate_weights

logger = get_logger(__name__)


def _validate_coordinates(lat: float, lng: float) -> None:
    """Check lat/lng are within India bounds."""
    if not (-8.0 <= lat <= 37.0 and 68.0 <= lng <= 97.0):
        raise InvalidCoordinatesError(lat, lng)


async def orchestrator_node(state: AgentState) -> dict:
    """
    Orchestrator node — deterministic routing logic.

    Responsibilities:
    1. Validate site_input coordinates (India bounds).
    2. Validate user_weights.
    3. Detect intent from request context.
    4. Set current_node and return updated state.
    """
    updates: dict = {"current_node": "orchestrator"}
    logger.info("Orchestrator node invoked")

    try:
        # ── 1. Validate coordinates ──────────────────────────────────
        site_input = state.get("site_input")
        if site_input is not None:
            _validate_coordinates(site_input.lat, site_input.lng)

        # ── 2. Validate weights ──────────────────────────────────────
        user_weights = state.get("user_weights")
        weights_valid = False

        if user_weights is not None:
            weight_dict = user_weights.model_dump()
            is_valid, error_msg = validate_weights(weight_dict)
            if not is_valid:
                logger.warning("Invalid weights rejected: %s", error_msg)
                updates["error"] = f"Invalid weights: {error_msg}"
                updates["intent"] = "error"
                return updates
            weights_valid = True

        # ── 3. Detect intent ─────────────────────────────────────────
        comparison_sites = state.get("comparison_sites")

        if state.get("request_explanation") and site_input is not None:
            updates["intent"] = "explain_result"

        elif comparison_sites and len(comparison_sites) >= 1:
            updates["intent"] = "compare_sites"

        elif site_input is None:
            # No site provided — hotspot query
            updates["intent"] = "find_hotspots"

        elif not weights_valid:
            # No weights → ask advisory agent
            updates["intent"] = "advise_weights"

        else:
            # Single site + valid weights → score it
            updates["intent"] = "score_site"

        logger.info("Intent detected: %s", updates.get("intent", "unknown"))

    except InvalidCoordinatesError as exc:
        logger.error("Orchestrator validation error: %s", exc)
        updates["error"] = str(exc)
        updates["intent"] = "error"

    return updates
