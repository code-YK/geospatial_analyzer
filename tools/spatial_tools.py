"""
tools/spatial_tools.py — H3 indexing + PostGIS spatial queries.
"""

from typing import List, Optional, Tuple

import h3
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
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


# ── H3 Utilities ──────────────────────────────────────────────────────────

def lat_lng_to_h3(lat: float, lng: float, resolution: int = 8) -> str:
    """Convert lat/lng to an H3 index at the given resolution."""
    return h3.latlng_to_cell(lat, lng, resolution)


def h3_to_lat_lng(h3_id: str) -> Tuple[float, float]:
    """Get centroid (lat, lng) from an H3 index."""
    lat, lng = h3.cell_to_latlng(h3_id)
    return lat, lng


# ── Database Spatial Queries ──────────────────────────────────────────────

async def get_neighboring_cells(
    h3_id: str,
    k_rings: int = 2,
    db: Optional[AsyncSession] = None,
) -> List[SiteFeatures]:
    """
    Return k-ring neighbours of a cell from the database.

    Uses the H3 library to compute neighbour IDs, then fetches matching
    rows from PostgreSQL.
    """
    neighbor_ids = list(h3.grid_disk(h3_id, k_rings))

    if db is None:
        return []

    placeholders = ", ".join(f":id_{i}" for i in range(len(neighbor_ids)))
    query = text(f"SELECT * FROM site_features WHERE grid_id IN ({placeholders})")
    params = {f"id_{i}": nid for i, nid in enumerate(neighbor_ids)}

    result = await db.execute(query, params)
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
    For a given state, fetch all H3 cells, compute final scores,
    and return the top_n cells ranked by site_readiness_score.

    Uses PostGIS spatial index for efficient state-level querying.
    """
    if db is None:
        return []

    query = text(
        """
        SELECT grid_id, latitude, longitude, state, district, area_name,
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
            grid_id=row_dict["grid_id"],
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
                grid_id=row_dict["grid_id"],
                lat=row_dict.get("latitude", 0) or 0,
                lng=row_dict.get("longitude", 0) or 0,
                state=row_dict.get("state", ""),
                district=row_dict.get("district", ""),
                area_name=row_dict.get("area_name", ""),
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
    h3_id: str,
    radius_km: float,
    db: Optional[AsyncSession] = None,
) -> CatchmentResult:
    """
    Return all H3 cells within ``radius_km`` of the given cell.

    Uses PostGIS ``ST_DWithin`` for the spatial query.
    """
    center_lat, center_lng = h3_to_lat_lng(h3_id)
    radius_meters = radius_km * 1000.0

    if db is None:
        return CatchmentResult(
            center_h3_id=h3_id,
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
        {"lat": center_lat, "lng": center_lng, "radius_m": radius_meters},
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
        center_h3_id=h3_id,
        radius_km=radius_km,
        cell_count=len(cells),
        cells=cells,
        avg_score=avg_score,
    )
