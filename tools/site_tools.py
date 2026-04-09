"""
tools/site_tools.py — Database fetch functions for site features and scores.

Uses direct H3 grid_id lookup (O(1)) rather than ST_NearestNeighbor.
"""

from typing import Optional

import h3
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.exceptions import SiteNotFoundError
from core.logger import get_logger
from models.site import PrecomputedScores, SiteFeatures

logger = get_logger(__name__)


async def fetch_site_features(
    lat: float,
    lng: float,
    h3_id: Optional[str],
    db: AsyncSession,
) -> SiteFeatures:
    """
    Query PostgreSQL for all columns for the nearest H3 cell.

    - If ``h3_id`` is provided: direct lookup by grid_id.
    - If only lat/lng: use H3 library to compute h3_id at the configured
      resolution, then lookup.

    Raises
    ------
    SiteNotFoundError
        If no matching row is found.
    """
    if h3_id is None:
        settings = get_settings()
        h3_id = h3.latlng_to_cell(lat, lng, settings.h3_resolution)
        logger.debug("Computed H3 cell %s from lat=%.4f, lng=%.4f", h3_id, lat, lng)

    logger.info("Fetching site features for H3 cell: %s", h3_id)
    query = text("SELECT * FROM site_features WHERE grid_id = :grid_id LIMIT 1")
    result = await db.execute(query, {"grid_id": h3_id})
    row = result.mappings().fetchone()

    if row is None:
        logger.warning("Site not found for H3 cell: %s", h3_id)
        raise SiteNotFoundError(h3_id)

    logger.info("Site features loaded for %s", h3_id)

    return SiteFeatures(**dict(row))


async def fetch_precomputed_scores(
    h3_id: str,
    db: AsyncSession,
) -> PrecomputedScores:
    """
    Fetch Layer 7 precomputed scores for the given H3 cell.

    These scores are already normalised to 0–100 and stored in the
    ``site_features`` table.

    Raises
    ------
    SiteNotFoundError
        If no matching row is found.
    """
    query = text(
        """
        SELECT grid_id,
               demand_score,
               accessibility_score,
               competition_score,
               suitability_score,
               risk_score,
               infrastructure_score
        FROM site_features
        WHERE grid_id = :grid_id
        LIMIT 1
        """
    )
    result = await db.execute(query, {"grid_id": h3_id})
    row = result.mappings().fetchone()

    if row is None:
        logger.warning("Precomputed scores not found for H3 cell: %s", h3_id)
        raise SiteNotFoundError(h3_id)

    logger.info("Precomputed scores loaded for %s", h3_id)

    return PrecomputedScores(**dict(row))
