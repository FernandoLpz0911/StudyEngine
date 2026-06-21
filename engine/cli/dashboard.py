"""Progress dashboard: python -m engine.cli.dashboard [--subject diffeq].

Prints data-based readiness per subject (and per concept with --subject). All
figures come from measured accuracy and FSRS retention — nothing self-reported.
"""
from __future__ import annotations

import argparse

from engine.analytics.readiness import overall_progress, subject_readiness
from engine.db.seed import load_all
from engine.subjects import SUBJECTS


def _bar(fraction: float, width: int = 18) -> str:
    filled = round(max(0.0, min(1.0, fraction)) * width)
    return "█" * filled + "░" * (width - filled)


def _pct(fraction: float) -> str:
    return f"{round(fraction * 100):3d}%"


def _dkt_status_line() -> str:
    from engine.config import DKT_MIN_INTERACTIONS
    from engine.db import dao
    from engine.tracing import infer

    if infer.dkt_is_active():
        return "DKT: active — the global model is driving selection."
    n = dao.count_answered_interactions()
    return f"DKT: warming up — {n}/{DKT_MIN_INTERACTIONS} interactions until it activates."


def _print_subject_summary(s: dict) -> None:
    title = SUBJECTS[s["subject"]].title if s["subject"] in SUBJECTS else s["subject"]
    print(f"\n{title}")
    print(f"  [{_bar(s['readiness'])}] {_pct(s['readiness'])} ready")
    print(
        f"  seen {s['seen']}/{s['n_concepts']} · mastered {s['mastered']} · "
        f"due {s['due']} · answered {s['answered']} "
        f"({round(s['accuracy'] * 100)}% correct)"
    )


def _print_concepts(s: dict) -> None:
    for c in sorted(s["concepts"], key=lambda r: r["mastery"]):
        flag = "due" if c["due"] else ""
        seen = f"{c['reps']} reps" if c["reps"] else "unseen"
        print(
            f"   [{_bar(c['mastery'], 10)}] {_pct(c['mastery'])}  "
            f"{c['name'][:38]:38} ({c['mode']}, {seen}) {flag}"
        )


def run(subject: str | None) -> None:
    load_all()
    if subject:
        if subject not in SUBJECTS:
            print(f"Unknown subject '{subject}'. Choose from: {', '.join(SUBJECTS)}")
            return
        s = subject_readiness(subject)
        _print_subject_summary(s)
        _print_concepts(s)
        return

    progress = overall_progress(list(SUBJECTS))
    print("=== StudyEngine — Progress Dashboard ===")
    print(
        f"Combined readiness: [{_bar(progress['combined_readiness'])}] "
        f"{_pct(progress['combined_readiness'])}"
    )
    print(_dkt_status_line())
    for s in progress["subjects"]:
        _print_subject_summary(s)
    print("\nRun with --subject <key> for per-concept detail.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Show study progress / readiness.")
    parser.add_argument("--subject", choices=list(SUBJECTS), default=None)
    args = parser.parse_args()
    run(args.subject)


if __name__ == "__main__":
    main()
