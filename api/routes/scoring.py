"""
api/routes/scoring.py — /score endpoints.

POST /score         → Full LangGraph graph run for a single site
POST /score/what-if → What-if weight comparison
"""

import uuid

from fastapi import APIRouter, HTTPException

from agents.graph import get_compiled_graph
from models.request import (
    ScoreRequest,
    ScoreResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from tools.explainability_tools import what_if_analysis
from tools.site_tools import fetch_precomputed_scores
from core.database import get_session_factory

router = APIRouter(prefix="/score", tags=["Scoring"])


@router.post(
    "",
    response_model=ScoreResponse,
    summary="Score a single site",
)
async def score_site(request: ScoreRequest) -> ScoreResponse:
    """
    Trigger the full LangGraph graph run for a single site.

    Returns the SiteScore, ScoreBreakdown, and insight text.
    """
    compiled = get_compiled_graph()
    thread_id = str(uuid.uuid4())

    initial_state = {
        "thread_id": thread_id,
        "use_case": request.use_case,
        "site_input": request.site_input,
        "user_weights": request.weights,
    }

    try:
        result = await compiled.ainvoke(initial_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {exc}")

    error = result.get("error")
    if error:
        raise HTTPException(status_code=400, detail=error)

    # Build response from graph output
    from models.site import SiteScore, ScoreBreakdown
    from tools.scoring_tools import compute_final_score

    precomputed = result.get("precomputed_scores")
    user_weights = result.get("user_weights")
    features = result.get("site_features")

    if precomputed is None or user_weights is None:
        raise HTTPException(status_code=500, detail="Scoring data incomplete")

    site_score = compute_final_score(
        precomputed_scores=precomputed,
        user_weights=user_weights,
        lat=features.latitude if features else 0,
        lng=features.longitude if features else 0,
    )

    return ScoreResponse(
        site_score=site_score,
        score_breakdown=result.get("score_breakdown"),
        insight_text=result.get("insight_text", ""),
        advisory_text=result.get("advisory_text"),
    )


@router.post(
    "/what-if",
    response_model=WhatIfResponse,
    summary="What-if weight comparison",
)
async def score_what_if(request: WhatIfRequest) -> WhatIfResponse:
    """
    Compare scores under two different weight configurations.
    """
    try:
        factory = get_session_factory()
        async with factory() as db:
            precomputed = await fetch_precomputed_scores(request.site_id, db)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Site not found: {exc}")

    result = what_if_analysis(
        precomputed_scores=precomputed,
        current_weights=request.current_weights,
        modified_weights=request.modified_weights,
    )

    return WhatIfResponse(result=result)


