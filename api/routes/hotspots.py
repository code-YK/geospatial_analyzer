"""
api/routes/hotspots.py — /hotspots endpoints.

POST /hotspots → Find top-N hotspot locations in a state for a use case.
"""

import uuid

from fastapi import APIRouter, HTTPException

from agents.graph import get_compiled_graph
from models.request import HotspotRequest, HotspotResponse
from models.site import SiteInput

router = APIRouter(prefix="/hotspots", tags=["Hotspots"])


@router.post(
    "",
    response_model=HotspotResponse,
    summary="Find hotspot locations",
)
async def find_hotspots(request: HotspotRequest) -> HotspotResponse:
    """
    Find the top-N hotspot locations in a state for a given use case.

    Triggers the full LangGraph graph with ``find_hotspots`` intent.
    """
    compiled = get_compiled_graph()
    thread_id = str(uuid.uuid4())

    # For hotspots, we don't have a specific site — use a dummy input
    # The geospatial node will use the state name for the query
    initial_state = {
        "thread_id": thread_id,
        "use_case": request.use_case,
        "site_input": None,
        "user_weights": request.weights,
    }

    try:
        result = await compiled.ainvoke(initial_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {exc}")

    error = result.get("error")
    if error:
        raise HTTPException(status_code=400, detail=error)

    return HotspotResponse(
        hotspots=result.get("hotspot_results", []),
        insight_text=result.get("insight_text", ""),
    )
