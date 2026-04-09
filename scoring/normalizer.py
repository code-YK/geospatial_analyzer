"""
scoring/normalizer.py — Feature normalization functions.

Used during ETL pipeline (separate) and referenced by the scoring engine
for documentation / online re-normalization.
"""

import math


def minmax_normalize(value: float, min_val: float, max_val: float) -> float:
    """
    Scale *value* to the 0–100 range using min-max normalization.

    Returns 0.0 if min_val == max_val (edge case: constant feature).
    """
    if math.isclose(min_val, max_val):
        return 0.0
    return ((value - min_val) / (max_val - min_val)) * 100.0


def clip_and_normalize(value: float, min_val: float, max_val: float) -> float:
    """
    Clip outliers to [min_val, max_val], then normalise to 0–100.
    """
    clipped = max(min_val, min(value, max_val))
    return minmax_normalize(clipped, min_val, max_val)


def invert_score(score: float) -> float:
    """
    For dimensions where higher raw value = worse outcome (e.g. risk,
    competition).

    Returns ``100 - score`` so that a higher output = better.
    """
    return 100.0 - score
