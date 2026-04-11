"""
tools/config_tools.py — Weight validation and default config helpers.
"""

from typing import Optional, Tuple

from models.weights import WeightConfig
from scoring.weights import USE_CASE_CATALOG

REQUIRED_KEYS = [
    "demand_score",
    "accessibility_score",
    "competition_score",
    "suitability_score",
    "risk_score",
    "infrastructure_score",
]


def get_default_weights(use_case: str) -> WeightConfig:
    """
    Return the hardcoded default WeightConfig for a given use case.

    Raises
    ------
    ValueError
        If the use case is not recognised.
    """
    if use_case not in USE_CASE_CATALOG:
        raise ValueError(
            f"Unknown use case '{use_case}'. "
            f"Valid options: {sorted(USE_CASE_CATALOG.keys())}"
        )
    return USE_CASE_CATALOG[use_case].weights


def validate_weights(weights: dict) -> Tuple[bool, Optional[str]]:
    """
    Validate a weight dictionary.

    Checks
    ------
    1. All 6 required keys are present.
    2. All values are between 0.0 and 1.0.
    3. Sum equals 1.0 (±0.01 tolerance).

    Returns
    -------
    (is_valid, error_message)
        ``(True, None)`` if valid, ``(False, "reason")`` otherwise.
    """
    # Check required keys
    missing = [k for k in REQUIRED_KEYS if k not in weights]
    if missing:
        return False, f"Missing weight keys: {missing}"

    # Check value ranges
    for key in REQUIRED_KEYS:
        val = weights[key]
        if not isinstance(val, (int, float)):
            return False, f"Weight '{key}' must be a number, got {type(val).__name__}"
        if not (0.0 <= val <= 1.0):
            return False, f"Weight '{key}' = {val} is outside [0.0, 1.0]"

    # Check sum
    total = sum(weights[k] for k in REQUIRED_KEYS)
    if not (0.99 <= total <= 1.01):
        return False, f"Weights sum to {total:.3f}, must be 1.0 (±0.01)"

    return True, None


def normalize_weights(weights: dict) -> WeightConfig:
    """
    Force weights to sum to 1.0 by proportional normalization.

    Useful when the advisory LLM returns weights that don't quite sum to 1.0.
    """
    total = sum(weights.get(k, 0.0) for k in REQUIRED_KEYS)
    if total == 0:
        # Equal distribution fallback
        equal = 1.0 / len(REQUIRED_KEYS)
        return WeightConfig(**{k: round(equal, 4) for k in REQUIRED_KEYS})

    normalized = {k: round(weights.get(k, 0.0) / total, 4) for k in REQUIRED_KEYS}

    # Adjust last element to ensure exact sum of 1.0
    residual = 1.0 - sum(v for k, v in normalized.items() if k != REQUIRED_KEYS[-1])
    normalized[REQUIRED_KEYS[-1]] = round(residual, 4)

    return WeightConfig(**normalized)
