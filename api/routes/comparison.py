"""
api/routes/comparison.py — /compare endpoints.

POST /compare → Compare and rank 2–5 sites for a given use case.
"""

import uuid

from fastapi import APIRouter, HTTPException

from agents.graph import get_compiled_graph
from models.request import CompareRequest, CompareResponse

router = APIRouter(prefix="/compare", tags=["Comparison"])


@router.post(
    "",
    response_model=CompareResponse,
    summary="Compare multiple sites",
)
async def compare_sites(request: CompareRequest) -> CompareResponse:
    """
    Compare 2–5 sites for a given use case.

    Triggers the full LangGraph graph with ``compare_sites`` intent.
    Returns ranked site scores and insight text.
    """
    compiled = get_compiled_graph()
    thread_id = str(uuid.uuid4())

    # First site is the primary; rest are comparison targets
    primary = request.sites[0]
    comparison = request.sites[1:]

    initial_state = {
        "thread_id": thread_id,
        "use_case": request.use_case,
        "site_input": primary,
        "user_weights": request.weights,
        "comparison_sites": comparison,
    }

    try:
        result = await compiled.ainvoke(initial_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {exc}")

    error = result.get("error")
    if error:
        raise HTTPException(status_code=400, detail=error)

    return CompareResponse(
        ranked_sites=result.get("comparison_results", []),
        insight_text=result.get("insight_text", ""),
    )
