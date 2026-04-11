"""
api/routes/sites.py — /sites endpoints.

GET  /sites/{site_id}          → fetch all features for a site by ID
GET  /sites/nearest?lat=&lng=  → find nearest site by coordinates
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from core.exceptions import SiteNotFoundError
from models.site import SiteFeatures
from tools.site_tools import fetch_site_features

router = APIRouter(prefix="/sites", tags=["Sites"])


@router.get(
    "/{site_id}",
    response_model=SiteFeatures,
    summary="Get site features by ID",
)
async def get_site_by_id(
    site_id: str,
    db: AsyncSession = Depends(get_db),
) -> SiteFeatures:
    """Fetch all feature columns for a specific site by its ID."""
    try:
        query = text("SELECT * FROM site_features WHERE id = :site_id LIMIT 1")
        result = await db.execute(query, {"site_id": site_id})
        row = result.mappings().fetchone()

        if row is None:
            raise SiteNotFoundError(site_id)

        return SiteFeatures(**dict(row))
    except SiteNotFoundError:
        raise HTTPException(status_code=404, detail=f"Site not found: {site_id}")


@router.get(
    "/nearest/",
    response_model=SiteFeatures,
    summary="Find nearest site by coordinates",
)
async def get_nearest_site(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    db: AsyncSession = Depends(get_db),
) -> SiteFeatures:
    """Find the nearest site for given lat/lng and return all features."""
    try:
        return await fetch_site_features(lat=lat, lng=lng, db=db)
    except SiteNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"No site found near coordinates ({lat}, {lng})",
        )
