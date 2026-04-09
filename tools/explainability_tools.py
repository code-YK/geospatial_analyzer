"""
tools/explainability_tools.py — Score breakdown and what-if analysis.
"""

from typing import Dict, List

from models.site import (
    PrecomputedScores,
    ScoreBreakdown,
    ScoreContribution,
    SiteScore,
    WhatIfResult,
)
from models.weights import WeightConfig
from scoring.engine import compute_final_score


def score_breakdown(site_score: SiteScore) -> ScoreBreakdown:
    """
    Build a full explainability breakdown from a SiteScore.

    For each dimension, shows the raw score, applied weight, weighted
    contribution, and rank among the six dimensions.

    Strengths = top 2 contributors.  Weaknesses = bottom 2 contributors.
    """
    precomputed = site_score.precomputed_scores
    weights = site_score.weights_used

    dimension_data: Dict[str, dict] = {
        "demand_score": {
            "raw": precomputed.demand_score,
            "weight": weights.demand_score,
        },
        "accessibility_score": {
            "raw": precomputed.accessibility_score,
            "weight": weights.accessibility_score,
        },
        "competition_score": {
            "raw": precomputed.competition_score,
            "weight": weights.competition_score,
        },
        "suitability_score": {
            "raw": precomputed.suitability_score,
            "weight": weights.suitability_score,
        },
        "risk_score": {
            "raw": precomputed.risk_score,
            "weight": weights.risk_score,
        },
        "infrastructure_score": {
            "raw": precomputed.infrastructure_score,
            "weight": weights.infrastructure_score,
        },
    }

    # Calculate contributions
    contributions_list: List[tuple] = []
    for name, data in dimension_data.items():
        contribution = round(data["raw"] * data["weight"], 2)
        contributions_list.append((name, data["raw"], data["weight"], contribution))

    # Sort by contribution descending for ranking
    contributions_list.sort(key=lambda x: x[3], reverse=True)

    contributions: Dict[str, ScoreContribution] = {}
    for rank, (name, raw, weight, contribution) in enumerate(contributions_list, start=1):
        contributions[name] = ScoreContribution(
            raw=raw,
            weight=weight,
            contribution=contribution,
            rank=rank,
        )

    # Strengths = top 2, Weaknesses = bottom 2
    strengths = [contributions_list[i][0] for i in range(min(2, len(contributions_list)))]
    weaknesses = [contributions_list[-(i + 1)][0] for i in range(min(2, len(contributions_list)))]

    return ScoreBreakdown(
        site_readiness_score=site_score.site_readiness_score,
        contributions=contributions,
        strengths=strengths,
        weaknesses=weaknesses,
    )


def what_if_analysis(
    precomputed_scores: PrecomputedScores,
    current_weights: WeightConfig,
    modified_weights: WeightConfig,
) -> WhatIfResult:
    """
    Compute score under both weight configs.

    Returns the delta and per-dimension gain/loss.
    """
    original = compute_final_score(precomputed_scores, current_weights)
    modified = compute_final_score(precomputed_scores, modified_weights)

    dimension_deltas: Dict[str, float] = {}
    for dim_name in original.contributions:
        orig_contrib = original.contributions.get(dim_name, 0.0)
        mod_contrib = modified.contributions.get(dim_name, 0.0)
        dimension_deltas[dim_name] = round(mod_contrib - orig_contrib, 2)

    return WhatIfResult(
        original_score=original.site_readiness_score,
        modified_score=modified.site_readiness_score,
        delta=round(modified.site_readiness_score - original.site_readiness_score, 2),
        dimension_deltas=dimension_deltas,
    )
