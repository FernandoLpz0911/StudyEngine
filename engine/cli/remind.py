"""Desktop review nudge: python -m engine.cli.remind.

Local-first reminder for when the app is closed — meant to be run from cron (e.g.
hourly). Prints how many FSRS reviews are due and whether today's streak is still
unprotected, and fires a desktop notification via `notify-send` when available so
the open loop pulls the learner back. Exits 0 with no output when nothing is due
(quiet for cron unless --force).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess

import engine.subjects  # noqa: F401  (registers generators; ensures concepts load)
from engine.db import dao
from engine.db.seed import load_all


def _notify(title: str, body: str) -> None:
    """Best-effort desktop notification; silently degrade if unsupported."""
    notify_send = shutil.which("notify-send")
    if notify_send:
        subprocess.run([notify_send, title, body], check=False)


def run(force: bool = False) -> None:
    load_all()
    due = dao.due_count()
    streak = dao.daily_streak()
    studied_today = dao.count_answered_today() > 0

    if due == 0 and studied_today and not force:
        return  # caught up and habit kept — stay quiet for cron

    parts = [f"{due} review(s) due" if due else "no reviews due"]
    if streak and not studied_today:
        parts.append(f"protect your {streak}-day streak 🔥")
    elif not studied_today:
        parts.append("start a streak today")
    body = " · ".join(parts)

    print(f"StudyEngine: {body}")
    _notify("StudyEngine", body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Desktop nudge for due reviews.")
    parser.add_argument(
        "--force", action="store_true", help="notify even when caught up"
    )
    args = parser.parse_args()
    run(force=args.force)


if __name__ == "__main__":
    main()
