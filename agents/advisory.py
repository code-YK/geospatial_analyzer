"""
agents/advisory.py — LLM weight advisor node.

Uses the LLM to suggest scoring weights based on the business use case.
Only called when user has NOT provided weights.
"""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import AgentState
from core.logger import get_logger
from llm.llm_config import get_llm
from llm.prompts import ADVISORY_SYSTEM_PROMPT, ADVISORY_USER_PROMPT
from models.weights import WeightConfig
from tools.config_tools import get_default_weights, normalize_weights

logger = get_logger(__name__)


async def advisory_node(state: AgentState) -> dict:
    """
    Advisory node — suggests weights based on use case via LLM.

    Steps:
    1. Call LLM with structured JSON prompt.
    2. Parse the returned JSON.
    3. Validate weights sum to 1.0 (normalize if needed).
    4. Set recommended_weights, advisory_text, and user_weights.
    """
    updates: dict = {"current_node": "advisory"}
    use_case = state.get("use_case", "retail")

    try:
        llm = get_llm()
        logger.info("Advisory LLM call started for use_case=%s", use_case)

        messages = [
            SystemMessage(content=ADVISORY_SYSTEM_PROMPT),
            HumanMessage(content=ADVISORY_USER_PROMPT.format(use_case=use_case)),
        ]

        response = await llm.ainvoke(messages)
        content = response.content.strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3].strip()
        if content.startswith("json"):
            content = content[4:].strip()

        parsed = json.loads(content)
        rec_weights = parsed.get("recommended_weights", {})
        reasoning = parsed.get("reasoning", "")

        # Validate and normalize
        total = sum(rec_weights.values())
        if not (0.99 <= total <= 1.01):
            logger.warning(
                "Advisory weights sum to %.3f — normalizing", total
            )
            weight_config = normalize_weights(rec_weights)
        else:
            weight_config = WeightConfig(**rec_weights)

        updates["recommended_weights"] = weight_config
        updates["user_weights"] = weight_config
        updates["advisory_text"] = reasoning
        logger.info(
            "Advisory weights recommended: %s",
            weight_config.model_dump(),
        )

    except Exception as exc:
        logger.error("Advisory LLM call failed: %s — falling back to defaults", exc)

        # Fallback to hardcoded defaults
        fallback = get_default_weights(use_case)
        updates["recommended_weights"] = fallback
        updates["user_weights"] = fallback
        updates["advisory_text"] = (
            f"Using default weights for '{use_case}' "
            f"(LLM advisory unavailable: {exc})"
        )

    return updates
