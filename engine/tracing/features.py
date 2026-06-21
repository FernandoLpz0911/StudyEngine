"""Per-step temporal features appended to the DKT one-hot input.

Classic DKT ignores time, but recall depends on it. Each step contributes two
scalars derived from the concept's own history:

  - recall lag: log1p(days since this concept was last seen), so the model can
    learn forgetting between spaced reviews.
  - practice volume: log1p(number of prior attempts on this concept).

Both are lightly scaled into roughly [0, 1] so they sit on a comparable scale to
the binary one-hot entries.
"""
from __future__ import annotations

import math

N_DKT_FEATURES = 2
_LAG_SCALE = 6.0        # ≈ log1p(400 days)
_ATTEMPTS_SCALE = 5.0   # ≈ log1p(150 attempts)


def step_features(lag_days: float, prior_attempts: int) -> list[float]:
    """Temporal feature vector for a single step (see module docstring)."""
    lag = math.log1p(max(0.0, lag_days)) / _LAG_SCALE
    attempts = math.log1p(max(0, prior_attempts)) / _ATTEMPTS_SCALE
    return [lag, attempts]


def encode_features(steps: list[tuple[int, float]]) -> list[list[float]]:
    """Map a sequence of (concept_idx, time_days) to per-step temporal features.

    `time_days` may use any consistent epoch. For each step, lag is measured from
    the concept's previous occurrence (0 on first sight) and attempts counts the
    concept's prior occurrences in the sequence.
    """
    last_seen: dict[int, float] = {}
    attempts: dict[int, int] = {}
    out: list[list[float]] = []
    for concept_idx, t in steps:
        previous = last_seen.get(concept_idx)
        lag_days = 0.0 if previous is None else t - previous
        out.append(step_features(lag_days, attempts.get(concept_idx, 0)))
        last_seen[concept_idx] = t
        attempts[concept_idx] = attempts.get(concept_idx, 0) + 1
    return out
