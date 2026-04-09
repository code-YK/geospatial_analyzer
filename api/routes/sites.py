"""
api/routes/sites.py — /sites endpoints.

GET  /sites/{h3_id}           → fetch all features for a cell
GET  /sites/nearest?lat=&lng= → find nearest H3 cell and return features
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from core.exceptions import SiteNotFoundError
from models.site import SiteFeatures
from tools.site_tools import fetch_site_features

router = APIRouter(prefix="/sites", tags=["Sites"])


@router.get(
    "/{h3_id}",
    response_model=SiteFeatures,
    summary="Get site features by H3 grid ID",
)
async def get_site_by_h3(
    h3_id: str,
    db: AsyncSession = Depends(get_db),
) -> SiteFeatures:
    """Fetch all feature columns for a specific H3 cell."""
    try:
        return await fetch_site_features(lat=0, lng=0, h3_id=h3_id, db=db)
    except SiteNotFoundError:
        raise HTTPException(status_code=404, detail=f"Site not found: {h3_id}")


@router.get(
    "/nearest/",
    response_model=SiteFeatures,
    summary="Find nearest H3 cell by coordinates",
)
async def get_nearest_site(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    db: AsyncSession = Depends(get_db),
) -> SiteFeatures:
    """Find the nearest H3 cell for given lat/lng and return all features."""
    try:
        return await fetch_site_features(lat=lat, lng=lng, h3_id=None, db=db)
    except SiteNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"No site found near coordinates ({lat}, {lng})",
        )
