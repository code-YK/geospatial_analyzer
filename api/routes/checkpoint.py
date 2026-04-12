"""
api/routes/checkpoint.py — /checkpoint endpoints.

POST /checkpoint/score   → Structured entry, bypasses chat node
"""

import uuid

from fastapi import APIRouter, HTTPException

from agents.graph import get_compiled_graph
from models.request import CheckpointScoreRequest, CheckpointScoreResponse
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/checkpoint", tags=["Checkpoint"])


@router.post(
    "/score",
    response_model=CheckpointScoreResponse,
    summary="Score a site (structured, bypasses chat node)",
    description=(
        "Structured entry point for site scoring. Accepts lat/lng, use_case, "
        "and optional weights. Bypasses the conversational chat node and injects "
        "state directly at the orchestrator. Returns structured JSON output."
    ),
)
async def checkpoint_score(request: CheckpointScoreRequest):
    """
    Structured scoring endpoint — bypasses chat node LLM.

    Injects state with entry_point='checkpoint' so chat_node and
    orchestrator_node short-circuit directly to the score_site path.
    """
    thread_id = str(uuid.uuid4())
    logger.info(
        "Checkpoint score request | thread=%s | use_case=%s | lat=%s, lng=%s",
        thread_id, request.use_case,
        request.site_input.lat, request.site_input.lng,
    )

    initial_state = {
        "thread_id": thread_id,
        "entry_point": "checkpoint",
        "use_case": request.use_case,
        "site_input": request.site_input,
        "user_weights": request.weights,
        "conversation_history": [],
        "retry_count": 0,
        "analysis_complete": False,
    }

    compiled = get_compiled_graph()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = await compiled.ainvoke(initial_state, config=config)
    except Exception as exc:
        logger.error("Checkpoint score failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    # Surface error from graph if validation blocked the run
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    # Serialize structured output directly from state — no chat formatting
    return CheckpointScoreResponse(
        site_id=(
            result["site_features"].id if result.get("site_features") else None
        ),
        location=_build_location_label(result),
        use_case=request.use_case,
        final_score=result.get("final_score"),
        score_breakdown=result.get("score_breakdown"),
        weights_used=(
            result.get("user_weights") or result.get("recommended_weights")
        ),
        insight_text=result.get("insight_text"),
        advisory_text=result.get("advisory_text"),
        validation_warnings=result.get("validation_warnings", []),
        thread_id=thread_id,
    )


def _build_location_label(result: dict) -> str:
    """Build human-readable location from site_features."""
    sf = result.get("site_features")
    if not sf:
        return "Unknown location"
    parts = [p for p in [sf.district, sf.state] if p]
    return ", ".join(parts) if parts else "Unknown location"
