"""Rotating daily quests — variety on top of the flat daily goal.

Three quests are drawn deterministically from the pool each local day (seeded by
the date, so every surface shows the same set). Progress is computed straight
from today's interaction log; completing a quest banks a one-time XP bonus in
quest_log, which total_xp counts. No self-report anywhere.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from engine.db import dao
from engine.subjects import SUBJECTS

QUESTS_PER_DAY = 3
BONUS_XP = 25


@dataclass
class Quest:
    id: str
    name: str
    desc: str
    target: int
    progress: Callable[[], int]  # lazy: only evaluated for the day's drawn quests


def _pool(rows: list[dict], daily_goal: int, rng: np.random.Generator) -> list[Quest]:
    """Every defined quest; progress is lazy so undrawn quests cost nothing
    (clean_queue's due_count query in particular runs only when it is drawn)."""
    correct = [r for r in rows if r["is_correct"]]
    focus = str(rng.choice(sorted(SUBJECTS)))  # same subject all day (seeded rng)
    return [
        Quest("speed_five", "⚡ Quick five", "5 correct under 10s each", 5,
              lambda: sum(1 for r in correct if 0 < r["elapsed_ms"] < 10_000)),
        Quest("spread_three", "🌍 Globetrotter", "Study 3 different subjects", 3,
              lambda: len({r["subject"] for r in rows})),
        Quest(f"focus_{focus}", f"🎯 Focus: {focus}", f"5 correct in {focus}", 5,
              lambda: sum(1 for r in correct if r["subject"] == focus)),
        Quest("overachiever", "🔥 Overachiever", "Answer 150% of your daily goal",
              max(1, int(daily_goal * 1.5)), lambda: len(rows)),
        Quest("sharp_ten", "🎓 Sharp ten", "80%+ accuracy over 10+ answers", 1,
              lambda: 1 if len(rows) >= 10 and len(correct) / len(rows) >= 0.8 else 0),
        Quest("clean_queue", "🧹 Clean queue", "Finish with no reviews waiting", 1,
              lambda: 1 if rows and dao.due_count() == 0 else 0),
    ]


def _evaluate(
    rows: list[dict], day: str, claimed: set[str], daily_goal: int
) -> list[dict]:
    """Draw the day's quests, bank any newly completed bonus, return their state.

    Pure over its inputs (no queries of its own) so both the view and the answer
    path share one draw + one interaction scan + one claimed-set read.
    """
    rng = np.random.default_rng(int(day.replace("-", "")))
    pool = _pool(rows, daily_goal, rng)
    picks = rng.permutation(len(pool))[:QUESTS_PER_DAY]
    out = []
    for i in sorted(picks):
        q = pool[i]
        progress = q.progress()
        done = progress >= q.target
        if done and q.id not in claimed:
            dao.claim_quest(day, q.id, BONUS_XP)  # bank the bonus exactly once
        out.append({
            "id": q.id,
            "name": q.name,
            "desc": q.desc,
            "target": q.target,
            "progress": min(progress, q.target),
            "done": done,
            "bonus_xp": BONUS_XP,
        })
    return out


def todays_quests() -> list[dict]:
    """The day's three quests with progress and completion, bonuses auto-banked."""
    from engine import settings
    day = dao._local_today().isoformat()
    return _evaluate(
        dao.today_interactions(), day, dao.claimed_quests(day),
        settings.get_int("daily_goal"),
    )


def settle() -> None:
    """Bank any newly completed quests — the answer path's cheap entry point.

    Reads the claimed set once and early-outs when the day's draw is fully
    claimed, so a long session doesn't pay the pool computation on every answer.
    """
    from engine import settings
    day = dao._local_today().isoformat()
    claimed = dao.claimed_quests(day)
    if len(claimed) >= QUESTS_PER_DAY:
        return
    _evaluate(
        dao.today_interactions(), day, claimed, settings.get_int("daily_goal")
    )
