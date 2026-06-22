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


def _print_hud() -> None:
    from engine import stats
    p = stats.profile()
    streak = f"🔥 {p['streak_days']}-day streak" if p["streak_days"] else "no streak yet"
    goal = f"{p['answered_today']}/{p['daily_goal']}"
    waiting = f" · {p['due_count']} review(s) due" if p["due_count"] else ""
    print(
        f"{streak} · ⭐ Lvl {p['level']} ({p['xp_into_level']}/{p['xp_for_next']} XP) "
        f"· 🎯 {goal} today{waiting}\n"
    )


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


def _glyph(mastery: float) -> str:
    if mastery >= 0.8:
        return "█"
    if mastery >= 0.5:
        return "▓"
    if mastery >= 0.2:
        return "▒"
    return "░"


def _by_domain(subjects: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for s in subjects:
        grouped.setdefault(s.get("domain") or "Other", []).append(s)
    return grouped


def _render_map(progress: dict) -> None:
    print("=== Knowledge Map  (░ foggy · ▒ · ▓ · █ mastered) ===")
    concepts = [c for s in progress["subjects"] for c in s["concepts"]]
    total = len(concepts) or 1
    unfogged = sum(c["mastery"] for c in concepts) / total
    foggy = sum(1 for c in concepts if c["mastery"] == 0)
    tail = f"{foggy} still in the fog" if foggy else "every concept touched 🎉"
    print(f"[{_bar(unfogged)}] {_pct(unfogged)} unfogged · {tail}")
    print(_dkt_status_line())
    for domain in sorted(_by_domain(progress["subjects"])):
        print(f"\n{domain}")
        for s in _by_domain(progress["subjects"])[domain]:
            glyphs = "".join(_glyph(c["displayed"]) for c in s["concepts"])
            short = SUBJECTS[s["subject"]].title.split("—")[-1].strip()
            print(f"  {glyphs}  {short} ({_pct(s['readiness'])})")


def run(subject: str | None = None, show_map: bool = False) -> None:
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
    if show_map:
        _render_map(progress)
        return

    print("=== StudyEngine — Progress Dashboard ===")
    _print_hud()
    print(
        f"Combined readiness: [{_bar(progress['combined_readiness'])}] "
        f"{_pct(progress['combined_readiness'])}"
    )
    print(_dkt_status_line())
    for domain in sorted(_by_domain(progress["subjects"])):
        print(f"\n=== {domain} ===")
        for s in _by_domain(progress["subjects"])[domain]:
            _print_subject_summary(s)
    _print_extras()
    print("\n--subject <key> for per-concept detail · --map for the knowledge map.")


def _print_extras() -> None:
    from engine import stats
    from engine.db import dao
    bests = dao.personal_bests()
    fast = f"{bests['fastest_ms'] / 1000:.1f}s" if bests["fastest_ms"] else "—"
    print(
        f"\n=== Personal bests ===\n  fastest {fast} · best day {bests['best_day']} "
        f"· longest run {bests['longest_run']}"
    )
    earned = [a for a in stats.achievements() if a["earned"]]
    locked = [a for a in stats.achievements() if not a["earned"]]
    print("\n=== Achievements ===")
    print("  " + (" ".join(a["name"] for a in earned) if earned else "none yet"))
    if locked:
        nxt = locked[0]
        print(f"  next: {nxt['name']} — {nxt['desc']}")
    leeches = dao.leeches()
    if leeches:
        print("\n=== ⚠️ Leeches (repeatedly missed — add a mnemonic) ===")
        for ll in leeches[:5]:
            print(f"  {ll['lapses']}× {ll['name']} ({ll['subject']})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Show study progress / readiness.")
    parser.add_argument("--subject", choices=list(SUBJECTS), default=None)
    parser.add_argument("--map", action="store_true", help="render the knowledge map")
    args = parser.parse_args()
    run(args.subject, args.map)


if __name__ == "__main__":
    main()
