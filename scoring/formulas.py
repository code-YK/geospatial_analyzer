"""
scoring/formulas.py — Distance decay and derived score formulas.

Provides configurable decay functions used when composing raw features
into dimension scores during ETL or online re-scoring.
"""

import math


def distance_decay(
    distance_meters: float,
    decay_type: str = "inverse_square",
    decay_lambda: float = 0.001,
    max_distance: float = 5000.0,
) -> float:
    """
    Compute a distance-based weight in [0, 1].

    Parameters
    ----------
    distance_meters : float
        Distance in metres.
    decay_type : str
        One of:
        - ``"inverse_square"`` – weight = 1 / (1 + d²)  (strong local effects, POI)
        - ``"exponential"``   – weight = exp(-λ · d)     (gradual decay, demographics)
        - ``"linear"``        – weight = max(0, 1 - d/max_d)  (hard cutoff radius)
    decay_lambda : float
        Lambda parameter for exponential decay (default 0.001).
    max_distance : float
        Maximum distance for linear decay (default 5 000 m).

    Returns
    -------
    float
        Decay weight between 0.0 and 1.0.
    """
    d = max(0.0, distance_meters)

    if decay_type == "inverse_square":
        return 1.0 / (1.0 + d ** 2)

    elif decay_type == "exponential":
        return math.exp(-decay_lambda * d)

    elif decay_type == "linear":
        if max_distance <= 0:
            return 0.0
        return max(0.0, 1.0 - d / max_distance)

    else:
        raise ValueError(
            f"Unknown decay_type '{decay_type}'. "
            f"Choose from: inverse_square, exponential, linear"
        )
