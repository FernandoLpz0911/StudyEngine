"""Variable-reward feedback for the study loop (text only).

Unpredictable praise is more motivating than the same line every time, so a
correct answer earns an occasional varied note plus a streak milestone — a
variable-ratio schedule rather than constant reinforcement.
"""
from __future__ import annotations

import numpy as np

PRAISE = [
    "Nice.",
    "Clean.",
    "Locked in.",
    "Sharp — that one's sticking.",
    "Smooth.",
    "That's the pattern.",
]
PRAISE_PROBABILITY = 0.3
STREAK_MILESTONE = 5


def reward_message(correct: bool, streak: int, rng: np.random.Generator) -> str:
    """Occasional, unpredictable reinforcement for a correct answer ("" otherwise)."""
    if not correct:
        return ""
    if streak and streak % STREAK_MILESTONE == 0:
        return f"🔥 {streak} correct in a row!"
    if rng.random() < PRAISE_PROBABILITY:
        return str(rng.choice(PRAISE))
    return ""
