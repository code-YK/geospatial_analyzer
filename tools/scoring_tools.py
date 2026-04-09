"""
tools/scoring_tools.py — Thin wrappers around the deterministic scoring engine.
"""

from typing import List

from core.logger import get_logger
from models.site import PrecomputedScores, SiteScore
from models.weights import WeightConfig
from scoring.engine import (
    compute_final_score as _compute_final_score,
)

logger = get_logger(__name__)


def compute_final_score(
    precomputed_scores: PrecomputedScores,
    user_weights: WeightConfig,
    lat: float = 0.0,
    lng: float = 0.0,
) -> SiteScore:
    """
    Thin wrapper that calls ``scoring.engine.compute_final_score()``.
    """
    return _compute_final_score(
        precomputed_scores=precomputed_scores,
        user_weights=user_weights,
        lat=lat,
        lng=lng,
    )


def rank_sites(site_scores: List[SiteScore]) -> List[SiteScore]:
    """
    Sort sites by ``site_readiness_score`` descending.

    Returns a new list with rank order (index 0 = best).
    """
    return sorted(
        site_scores,
        key=lambda s: s.site_readiness_score,
        reverse=True,
    )
