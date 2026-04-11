"""
scoring/engine.py — Core deterministic scoring engine.

No LLM involvement. No randomness. Pure weighted-sum computation
with full contribution tracking for explainability.
"""

from core.logger import get_logger
from models.site import PrecomputedScores, SiteScore
from models.weights import WeightConfig

logger = get_logger(__name__)


def compute_final_score(
    precomputed_scores: PrecomputedScores,
    user_weights: WeightConfig,
    lat: float = 0.0,
    lng: float = 0.0,
) -> SiteScore:
    """
    Compute the final site readiness score (0–100) as a weighted sum
    of the six precomputed dimension scores.

    Formula
    -------
    site_readiness_score = Σ (dimension_score_i × weight_i)

    Also computes per-dimension weighted contributions for explainability.

    Parameters
    ----------
    precomputed_scores : PrecomputedScores
        Layer 7 scores (0–100 each).
    user_weights : WeightConfig
        Six weights summing to 1.0.
    lat, lng : float
        Coordinates for the output model.

    Returns
    -------
    SiteScore
        Final score plus contribution breakdown.
    """
    # Map dimension name → (raw score, weight)
    dimensions = {
        "demand_score": (precomputed_scores.demand_score, user_weights.demand_score),
        "accessibility_score": (precomputed_scores.accessibility_score, user_weights.accessibility_score),
        "competition_score": (precomputed_scores.competition_score, user_weights.competition_score),
        "suitability_score": (precomputed_scores.suitability_score, user_weights.suitability_score),
        "risk_score": (precomputed_scores.risk_score, user_weights.risk_score),
        "infrastructure_score": (precomputed_scores.infrastructure_score, user_weights.infrastructure_score),
    }

    contributions: dict[str, float] = {}
    total = 0.0

    for name, (raw, weight) in dimensions.items():
        contribution = raw * weight
        contributions[name] = round(contribution, 2)
        total += contribution

    site_readiness_score = round(total, 2)

    logger.info(
        "Score computed for %s: %.2f (contributions: %s)",
        precomputed_scores.id,
        site_readiness_score,
        contributions,
    )
    logger.debug(
        "Score breakdown — %s",
        " | ".join(f"{k}={v}" for k, v in contributions.items()),
    )

    return SiteScore(
        id=precomputed_scores.id,
        lat=lat,
        lng=lng,
        site_readiness_score=site_readiness_score,
        contributions=contributions,
        precomputed_scores=precomputed_scores,
        weights_used=user_weights,
    )
