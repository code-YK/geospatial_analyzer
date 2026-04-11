"""
tools/spatial_tools.py — PostGIS spatial queries.

All spatial operations use PostGIS. No H3 dependency.
"""

from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import get_logger
from models.site import (
    CatchmentResult,
    HotspotResult,
    PrecomputedScores,
    SiteFeatures,
)
from models.weights import WeightConfig
from scoring.engine import compute_final_score

logger = get_logger(__name__)


# ── Database Spatial Queries ──────────────────────────────────────────────

async def get_neighboring_sites(
    lat: float,
    lng: float,
    radius_km: float = 2.0,
    db: Optional[AsyncSession] = None,
) -> List[SiteFeatures]:
    """
    Return all sites within ``radius_km`` of the given coordinates.

    Uses PostGIS ``ST_DWithin`` for efficient spatial query.
    """
    if db is None:
        return []

    radius_meters = radius_km * 1000.0

    query = text("""
        SELECT *
        FROM site_features
        WHERE ST_DWithin(
            geom::geography,
            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
            :radius_m
        )
    """)
    result = await db.execute(
        query,
        {"lat": lat, "lng": lng, "radius_m": radius_meters},
    )
    rows = result.mappings().fetchall()

    return [SiteFeatures(**dict(row)) for row in rows]


async def detect_hotspots(
    state: str,
    use_case: str,
    user_weights: WeightConfig,
    top_n: int = 10,
    db: Optional[AsyncSession] = None,
) -> List[HotspotResult]:
    """
    For a given state, fetch all sites, compute final scores,
    and return the top_n sites ranked by site_readiness_score.

    Uses PostGIS spatial index for efficient state-level querying.
    """
    if db is None:
        return []

    query = text(
        """
        SELECT id, latitude, longitude, state, district,
               demand_score, accessibility_score, competition_score,
               suitability_score, risk_score, infrastructure_score
        FROM site_features
        WHERE LOWER(state) = LOWER(:state)
          AND demand_score IS NOT NULL
        """
    )
    result = await db.execute(query, {"state": state})
    rows = result.mappings().fetchall()

    hotspots: List[HotspotResult] = []

    for row in rows:
        row_dict = dict(row)
        precomputed = PrecomputedScores(
            id=row_dict["id"],
            demand_score=row_dict.get("demand_score", 0) or 0,
            accessibility_score=row_dict.get("accessibility_score", 0) or 0,
            competition_score=row_dict.get("competition_score", 0) or 0,
            suitability_score=row_dict.get("suitability_score", 0) or 0,
            risk_score=row_dict.get("risk_score", 0) or 0,
            infrastructure_score=row_dict.get("infrastructure_score", 0) or 0,
        )

        site_score = compute_final_score(
            precomputed_scores=precomputed,
            user_weights=user_weights,
            lat=row_dict.get("latitude", 0) or 0,
            lng=row_dict.get("longitude", 0) or 0,
        )

        hotspots.append(
            HotspotResult(
                id=row_dict["id"],
                lat=row_dict.get("latitude", 0) or 0,
                lng=row_dict.get("longitude", 0) or 0,
                state=row_dict.get("state", ""),
                district=row_dict.get("district", ""),
                site_readiness_score=site_score.site_readiness_score,
                precomputed_scores=precomputed,
            )
        )

    # Sort descending and take top N
    hotspots.sort(key=lambda h: h.site_readiness_score, reverse=True)
    result_list = hotspots[:top_n]
    logger.info(
        "Hotspot detection for state=%s: %d candidates, returning top %d",
        state, len(hotspots), len(result_list),
    )
    return result_list


async def catchment_analysis(
    lat: float,
    lng: float,
    site_id: str,
    radius_km: float,
    db: Optional[AsyncSession] = None,
) -> CatchmentResult:
    """
    Return all sites within ``radius_km`` of the given coordinates.

    Uses PostGIS ``ST_DWithin`` for the spatial query.
    """
    radius_meters = radius_km * 1000.0

    if db is None:
        return CatchmentResult(
            center_id=site_id,
            radius_km=radius_km,
            cell_count=0,
            cells=[],
        )

    query = text(
        """
        SELECT *
        FROM site_features
        WHERE ST_DWithin(
            geom::geography,
            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
            :radius_m
        )
        """
    )
    result = await db.execute(
        query,
        {"lat": lat, "lng": lng, "radius_m": radius_meters},
    )
    rows = result.mappings().fetchall()

    cells = [SiteFeatures(**dict(row)) for row in rows]

    # Compute average score if possible
    avg_score = None
    scores = [
        c.demand_score for c in cells
        if c.demand_score is not None
    ]
    if scores:
        avg_score = sum(scores) / len(scores)

    return CatchmentResult(
        center_id=site_id,
        radius_km=radius_km,
        cell_count=len(cells),
        cells=cells,
        avg_score=avg_score,
    )
