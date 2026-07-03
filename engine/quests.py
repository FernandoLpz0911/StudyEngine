"""Rotating daily quests — variety on top of the flat daily goal.

Three quests are drawn deterministically from the pool each local day (seeded by
the date, so every surface shows the same set). Progress is computed straight
from today's interaction log; completing a quest banks a one-time XP bonus in
quest_log, which total_xp counts. No self-report anywhere.
"""
from __future__ import annotations

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
    progress: int


def _pool(rows: list[dict], daily_goal: int, rng: np.random.Generator) -> list[Quest]:
    """Every defined quest with live progress; the day's draw picks from these."""
    correct = [r for r in rows if r["is_correct"]]
    subjects_touched = {r["subject"] for r in rows}
    focus = str(rng.choice(sorted(SUBJECTS)))  # same subject all day (seeded rng)
    accuracy_ok = len(rows) >= 10 and len(correct) / len(rows) >= 0.8
    return [
        Quest("speed_five", "⚡ Quick five", "5 correct under 10s each",
              5, sum(1 for r in correct if 0 < r["elapsed_ms"] < 10_000)),
        Quest("spread_three", "🌍 Globetrotter", "Study 3 different subjects",
              3, len(subjects_touched)),
        Quest(f"focus_{focus}", f"🎯 Focus: {focus}", f"5 correct in {focus}",
              5, sum(1 for r in correct if r["subject"] == focus)),
        Quest("overachiever", "🔥 Overachiever", "Answer 150% of your daily goal",
              max(1, int(daily_goal * 1.5)), len(rows)),
        Quest("sharp_ten", "🎓 Sharp ten", "80%+ accuracy over 10+ answers",
              1, 1 if accuracy_ok else 0),
        Quest("clean_queue", "🧹 Clean queue", "Finish with no reviews waiting",
              1, 1 if rows and dao.due_count() == 0 else 0),
    ]


def todays_quests() -> list[dict]:
    """The day's three quests with progress and completion, bonuses auto-banked."""
    from engine import settings
    day = dao._local_today().isoformat()
    rng = np.random.default_rng(int(day.replace("-", "")))
    pool = _pool(dao.today_interactions(), settings.get_int("daily_goal"), rng)
    picks = rng.permutation(len(pool))[:QUESTS_PER_DAY]
    claimed = dao.claimed_quests(day)
    out = []
    for i in sorted(picks):
        q = pool[i]
        done = q.progress >= q.target
        if done and q.id not in claimed:
            dao.claim_quest(day, q.id, BONUS_XP)  # bank the bonus exactly once
        out.append({
            "id": q.id,
            "name": q.name,
            "desc": q.desc,
            "target": q.target,
            "progress": min(q.progress, q.target),
            "done": done,
            "bonus_xp": BONUS_XP,
        })
    return out
