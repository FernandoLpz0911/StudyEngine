"""FSRS-5 forgetting curve — pure NumPy, cross-tested against py-fsrs.

The stability/difficulty updates are delegated to the ``fsrs`` library; this
module only exposes the retrievability curve and its inverse, used for urgency
ranking in the policy.
"""
from __future__ import annotations

DECAY: float = -0.5
FACTOR: float = 19.0 / 81.0  # guarantees R(S, S) = 0.90 exactly


def retrievability(elapsed_days: float, stability: float) -> float:
    """Probability of recall after `elapsed_days` given current stability.

    R(0, S) = 1.0; R(S, S) = 0.90 by definition of stability.
    """
    if stability <= 0:
        return 0.0
    return float((1.0 + FACTOR * elapsed_days / stability) ** DECAY)


def interval_for_target(stability: float, target_retention: float = 0.9) -> int:
    """Whole days until retrievability decays to `target_retention` (at least 1)."""
    if stability <= 0:
        return 1
    days = stability / FACTOR * (target_retention ** (1.0 / DECAY) - 1.0)
    return max(1, round(days))
