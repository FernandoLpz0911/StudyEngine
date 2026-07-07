"""Variable-reward feedback for the study loop (text only).

Unpredictable praise is more motivating than the same line every time, so a
correct answer earns an occasional varied note plus a streak milestone — a
variable-ratio schedule rather than constant reinforcement.
"""
from __future__ import annotations

from dataclasses import dataclass

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
    prev_run: int = 0,
) -> list[str]:
    """New personal bests set by the answer just given. Fires once at the
    *crossing*, not on every answer past it: `baselines` comes from
    dao.record_baselines (best_day excludes today) and is advanced in place —
    fastest_ms when beaten, longest_run when a run ends (`prev_run` is the run
    a wrong answer just broke), so a later shorter run can't refire a stale
    record.

    First-ever answers don't count as records (everything would be one).
    """
    records: list[str] = []
    fastest = baselines.get("fastest_ms")
    if correct and elapsed_ms > 0 and fastest and elapsed_ms < fastest:
        records.append(f"⚡ New record: fastest correct — {elapsed_ms / 1000:.1f}s")
        baselines["fastest_ms"] = elapsed_ms  # only a strictly faster answer refires
    longest = baselines.get("longest_run", 0)
    if not correct and prev_run > longest:
        baselines["longest_run"] = prev_run  # the record run just ended
    if correct and longest >= 3 and run_length == longest + 1:
        records.append(f"🏅 New record: longest run — ×{run_length}")
    best_day = baselines.get("best_day", 0)
    if best_day >= 5 and answered_today_before == best_day:
        records.append(f"📈 New record: biggest day — {answered_today_before + 1} answered")
    return records


@dataclass
class RecordTracker:
    """Live personal-best detection with a log-wide record run.

    Unlike the session combo streak, ``run`` counts consecutive correct answers
    across session boundaries (see docs/adr/0001) so a run that spans a restart
    can still set the longest-run record. Baselines advance in place as records
    are set, so each record fires once at its crossing.
    """

    fastest_ms: int | None
    best_day: int
    longest_run: int
    run: int = 0
    day: str = ""

    @classmethod
    def snapshot(cls) -> RecordTracker:
        """Build from the interaction log — baselines plus the trailing run."""
        from engine.db import dao
        return cls._from_baselines(dao.record_baselines())

    @classmethod
    def _from_baselines(cls, b: dict) -> RecordTracker:
        return cls(
            fastest_ms=b["fastest_ms"],
            best_day=b["best_day"],
            longest_run=b["longest_run"],
            run=b.get("current_run", 0),
            day=b.get("day", ""),
        )

    def refresh(self) -> None:
        """Re-snapshot when the local day has rolled over mid-session.

        A session left open past midnight would otherwise keep yesterday's
        best_day (which excluded yesterday) and fire a spurious daily record.
        The live run carries over — a correct streak isn't broken by midnight.
        """
        from engine.db import dao
        today = dao._local_today().isoformat()
        if self.day == today:
            return
        fresh = dao.record_baselines()
        self.fastest_ms = fresh["fastest_ms"]
        self.best_day = fresh["best_day"]
        self.longest_run = max(self.longest_run, fresh["longest_run"])
        self.day = fresh["day"]

    def detect(
        self, correct: bool, elapsed_ms: int, answered_today_before: int
    ) -> list[str]:
        records: list[str] = []
        if correct and elapsed_ms > 0 and self.fastest_ms and elapsed_ms < self.fastest_ms:
            records.append(f"⚡ New record: fastest correct — {elapsed_ms / 1000:.1f}s")
            self.fastest_ms = elapsed_ms  # only a strictly faster answer refires
        if correct:
            self.run += 1
            # Fire once at the crossing; a longer peak is banked when the run ends.
            if self.longest_run >= 3 and self.run == self.longest_run + 1:
                records.append(f"🏅 New record: longest run — ×{self.run}")
        else:
            self.longest_run = max(self.longest_run, self.run)  # bank the peak
            self.run = 0
        if self.best_day >= 5 and answered_today_before == self.best_day:
            records.append(
                f"📈 New record: biggest day — {answered_today_before + 1} answered"
            )
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
