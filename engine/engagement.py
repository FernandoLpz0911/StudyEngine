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


# Escalating in-session combo tiers (lowest threshold first). A live, named ramp
# turns a run of correct answers into rising tension toward the next tier — the
# slot-machine "almost there" pull, but earned only by genuine recall.
COMBO_TIERS: list[tuple[int, str]] = [
    (3, "🔥 Warm"),
    (5, "🔥🔥 Hot"),
    (8, "⚡ On fire"),
    (12, "💎 Unstoppable"),
    (20, "🌟 Godmode"),
]


def combo_label(streak: int) -> str:
    """Name for the current correct-answer run, or "" below the first tier."""
    label = ""
    for threshold, name in COMBO_TIERS:
        if streak >= threshold:
            label = name
    return label


# Triangular XP curve: advancing from level L to L+1 costs LEVEL_STEP × (L+1), so
# early levels arrive fast (momentum) and later ones stretch (long-term goal).
LEVEL_STEP = 100


def level_for_xp(xp: int) -> tuple[int, int, int]:
    """Map lifetime XP to (level, xp_into_level, xp_needed_for_next_level)."""
    level = 0
    remaining = max(0, xp)
    needed = LEVEL_STEP
    while remaining >= needed:
        remaining -= needed
        level += 1
        needed += LEVEL_STEP
    return level, remaining, needed
