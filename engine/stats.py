"""Learner-progression snapshot: streak, level, XP, daily goal, reviews waiting.

Pure aggregation over the interaction log and FSRS card states — no self-report.
Both the CLI and the HTTP API render the same profile so the motivational surface
is identical everywhere.
"""
from __future__ import annotations

from engine import settings
from engine.db import dao
from engine.engagement import level_for_xp


def profile() -> dict:
    """Everything the study UI needs to show "where you stand" at a glance."""
    xp = dao.total_xp()
    level, into, needed = level_for_xp(xp)
    answered_today = dao.count_answered_today()
    return {
        "xp": xp,
        "level": level,
        "xp_into_level": into,
        "xp_for_next": needed,
        "streak_days": dao.daily_streak(),
        "studied_today": answered_today > 0,
        "answered_today": answered_today,
        "daily_goal": settings.get_int("daily_goal"),
        "due_count": dao.due_count(),
        "freezes": dao.freeze_status()["earned"],
    }


def achievements() -> list[dict]:
    """Local badges derived purely from the log — milestones worth chasing.

    Each unearned badge carries its progress fraction: "5/7 days" pulls far harder
    than a grey trophy, so the near-misses are the point of the list.
    """
    p = profile()
    bests = dao.personal_bests()
    answered = dao.count_answered_interactions()
    days = len(dao.study_days())
    fastest = bests["fastest_ms"]
    # (id, name, desc, current, target); earned == current >= target.
    defs = [
        ("first_steps", "🎓 First Steps", "Answer your first item", answered, 1),
        ("century", "💯 Century", "Earn 100 XP", p["xp"], 100),
        ("level_5", "⭐ Rising", "Reach level 5", p["level"], 5),
        ("week_warrior", "🔥 Week Warrior", "7-day streak", p["streak_days"], 7),
        ("sharpshooter", "🎯 Sharpshooter", "10 correct in a row",
         bests["longest_run"], 10),
        ("dedicated", "📅 Dedicated", "Study on 30 days", days, 30),
        ("speed_demon", "⚡ Speed Demon", "Correct in under 3s",
         1 if fastest and fastest < 3000 else 0, 1),
    ]
    return [
        {
            "id": i,
            "name": n,
            "desc": d,
            "earned": current >= target,
            "progress": min(1.0, current / target),
            "progress_text": f"{min(current, target)}/{target}",
        }
        for i, n, d, current, target in defs
    ]


def me() -> dict:
    """Aggregate profile for the dashboard: stats, badges, bests, leeches, heatmap."""
    return {
        **profile(),
        "achievements": achievements(),
        "bests": dao.personal_bests(),
        "leeches": dao.leeches(),
        "heatmap": dao.study_days(),
    }
