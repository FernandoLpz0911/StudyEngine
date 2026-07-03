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


def detect_records(
    baselines: dict,
    answered_today_before: int,
    correct: bool,
    elapsed_ms: int,
    run_length: int,
) -> list[str]:
    """New personal bests set by the answer just given. Fires once at the
    *crossing*, not on every answer past it: `baselines` comes from
    dao.record_baselines (best_day excludes today, longest_run excludes the
    still-running streak) and fastest_ms is updated in place when beaten.

    First-ever answers don't count as records (everything would be one).
    """
    records: list[str] = []
    fastest = baselines.get("fastest_ms")
    if correct and elapsed_ms > 0 and fastest and elapsed_ms < fastest:
        records.append(f"⚡ New record: fastest correct — {elapsed_ms / 1000:.1f}s")
        baselines["fastest_ms"] = elapsed_ms  # only a strictly faster answer refires
    longest = baselines.get("longest_run", 0)
    if correct and longest >= 3 and run_length == longest + 1:
        records.append(f"🏅 New record: longest run — ×{run_length}")
    best_day = baselines.get("best_day", 0)
    if best_day >= 5 and answered_today_before == best_day:
        records.append(f"📈 New record: biggest day — {answered_today_before + 1} answered")
    return records


COMBO_BREAK_MIN = 3


def combo_break_message(prev_streak: int, best_streak: int) -> str:
    """Near-miss framing when a run ends — names what was lost so the re-chase
    starts immediately ("" below the noise threshold)."""
    if prev_streak < COMBO_BREAK_MIN:
        return ""
    tail = f" · best this session ×{best_streak}" if best_streak > prev_streak else ""
    return f"💔 combo ended at ×{prev_streak}{tail}"


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
