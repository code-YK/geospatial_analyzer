"""
tools/site_tools.py — Database fetch functions for site features and scores.

Uses PostGIS <-> operator for nearest-neighbor spatial lookup.
No H3 dependency.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import SiteNotFoundError
from core.logger import get_logger
from models.site import PrecomputedScores, SiteFeatures

logger = get_logger(__name__)


async def fetch_site_features(
    lat: float,
    lng: float,
    db: AsyncSession,
) -> SiteFeatures:
    """
    Find the nearest site_features row to the given lat/lng using PostGIS.

    Uses the ``<->`` operator with the GIST spatial index for fast
    nearest-neighbour lookup — no full table scan.

    Raises
    ------
    SiteNotFoundError
        If no matching row is found.
    """
    logger.info("Fetching site features for lat=%.4f, lng=%.4f", lat, lng)

    query = text("""
        SELECT *
        FROM site_features
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
        LIMIT 1;
    """)
    result = await db.execute(query, {"lat": lat, "lng": lng})
    row = result.mappings().fetchone()

    if row is None:
        logger.warning("Site not found near lat=%.4f, lng=%.4f", lat, lng)
        raise SiteNotFoundError(f"lat={lat}, lng={lng}")

    features = SiteFeatures(**dict(row))
    logger.info("Site features loaded for %s", features.id)

    return features


async def fetch_precomputed_scores(
    site_id: str,
    db: AsyncSession,
) -> PrecomputedScores:
    """
    Fetch Layer 7 precomputed scores for the given site ID.

    These scores are already normalised to 0–100 and stored in the
    ``site_features`` table.

    Raises
    ------
    SiteNotFoundError
        If no matching row is found.
    """
    query = text(
        """
        SELECT id,
               demand_score,
               accessibility_score,
               competition_score,
               suitability_score,
               risk_score,
               infrastructure_score
        FROM site_features
        WHERE id = :site_id
        LIMIT 1
        """
    )
    result = await db.execute(query, {"site_id": site_id})
    row = result.mappings().fetchone()

    if row is None:
        logger.warning("Precomputed scores not found for site: %s", site_id)
        raise SiteNotFoundError(site_id)

    logger.info("Precomputed scores loaded for %s", site_id)

    return PrecomputedScores(**dict(row))
