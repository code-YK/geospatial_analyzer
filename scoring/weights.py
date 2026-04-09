"""
scoring/weights.py — Default weight configurations per use case.

Hardcoded fallback weights. Advisory agent may override these.
"""

from models.weights import WeightConfig

# ── Default Weight Configurations ─────────────────────────────────────────

USE_CASE_WEIGHTS: dict[str, WeightConfig] = {
    "retail": WeightConfig(
        demand_score=0.30,
        accessibility_score=0.20,
        competition_score=0.20,
        suitability_score=0.10,
        risk_score=0.10,
        infrastructure_score=0.10,
    ),
    "ev_charging": WeightConfig(
        demand_score=0.25,
        accessibility_score=0.30,
        competition_score=0.05,
        suitability_score=0.10,
        risk_score=0.10,
        infrastructure_score=0.20,
    ),
    "warehouse": WeightConfig(
        demand_score=0.15,
        accessibility_score=0.35,
        competition_score=0.05,
        suitability_score=0.15,
        risk_score=0.15,
        infrastructure_score=0.15,
    ),
    "telecom": WeightConfig(
        demand_score=0.10,
        accessibility_score=0.25,
        competition_score=0.10,
        suitability_score=0.15,
        risk_score=0.15,
        infrastructure_score=0.25,
    ),
    "renewable": WeightConfig(
        demand_score=0.10,
        accessibility_score=0.20,
        competition_score=0.05,
        suitability_score=0.25,
        risk_score=0.20,
        infrastructure_score=0.20,
    ),
}

VALID_USE_CASES = list(USE_CASE_WEIGHTS.keys())
