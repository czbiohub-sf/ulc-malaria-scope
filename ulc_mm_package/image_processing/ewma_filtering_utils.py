import numpy as np


def ewma_update_step(prev_val: float, new_val: float, alpha: float) -> float:
    return prev_val * (1 - alpha) + new_val * alpha


def get_halflife_from_smoothing_factor(alpha: float) -> float:
    return -np.log(2) / np.log(1 - alpha)


def get_adjustment_period_ewma(alpha: float) -> int:
    """Get the period at which to take corrective steps.

    Returns twice the half-life of an EWMA filter given its smoothing factor alpha.
    """

    half_life = -np.log(2) / np.log(1 - alpha)
    return int(round(2 * half_life))
