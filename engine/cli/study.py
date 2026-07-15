"""Interactive study loop: python -m engine.cli.study --subject diffeq [--n 10].

Every item is objectively auto-graded — generator problems against their computed
answer, recall concepts against the correct multiple-choice option. There is no
self-rating: correctness plus response time alone derive the FSRS grade. Progress
persists in the SQLite database between runs.
"""
from __future__ import annotations

import argparse
import time

import engine.subjects  # noqa: F401  (registers the problem generators)
from engine import service, stats
from engine.db import dao
from engine.db.seed import load_all, load_subject
from engine.loop import Done, StudyLoop, Turn
from engine.service import GRADE_LABEL, LETTERS
from engine.subjects import SUBJECTS


def _print_hud() -> None:
    """Streak / level / daily goal banner — the 'where you stand' pull on entry."""
    p = stats.profile()
    bar_len = 16
    filled = round(bar_len * p["xp_into_level"] / p["xp_for_next"])
    xp_bar = "█" * filled + "░" * (bar_len - filled)
    streak = f"🔥 {p['streak_days']}-day streak" if p["streak_days"] else "no streak yet"
    print(
        f"\n{streak}  ·  ⭐ Lvl {p['level']}  [{xp_bar}] "
        f"{p['xp_into_level']}/{p['xp_for_next']} XP"
    )
    goal = f"{p['answered_today']}/{p['daily_goal']}"
    done = " ✓" if p["answered_today"] >= p["daily_goal"] else ""
    waiting = f"  ·  {p['due_count']} review(s) waiting" if p["due_count"] else ""
    print(f"Today: {goal} toward daily goal{done}{waiting}")
    from engine.quests import todays_quests
    for q in todays_quests():
        mark = "✓" if q["done"] else f"{q['progress']}/{q['target']}"
        print(f"   {q['name']} — {q['desc']}  [{mark}]  +{q['bonus_xp']} XP")


def _print_summary(label: str, answered: int, correct: int) -> None:
    """End-of-session card — the peak-end moment that decides if they come back."""
    if answered == 0:
        print("\nNo items this session.")
        return
    p = stats.profile()
    acc = int(100 * correct / answered)
    print(f"\n=== {label} ===")
    print(f"{correct}/{answered} correct  ·  {acc}%")
    streak_line = (
        f"🔥 {p['streak_days']}-day streak held"
        if p["streak_days"]
        else "streak starts tomorrow if you return"
    )
    print(f"⭐ Lvl {p['level']}  ({p['xp_into_level']}/{p['xp_for_next']} XP)  ·  {streak_line}")
    if p["answered_today"] >= p["daily_goal"]:
        print(f"🎯 Daily goal hit ({p['answered_today']}/{p['daily_goal']}).")
    else:
        left = p["daily_goal"] - p["answered_today"]
        print(f"🎯 {left} more to hit today's goal.")
    if p["due_count"]:
        print(f"↩️  {p['due_count']} review(s) still waiting — one more round?")


def _prompt(text: str) -> str:
    try:
        return input(text)
    except EOFError:
        return ""


def _run_item(loop: StudyLoop, turn: Turn) -> service.AnswerOutcome:
    """Render one served Turn, read the answer, and settle it through the loop."""
    item = turn.item
    typed = not item.choices
    print(f"\n[{item.concept_name}]  {item.question}")
    if typed:
        print("   ✍️  no options this time — you know this one; type the value")
    # Leech: repeatedly forgotten — slow down and re-read; more raw reps aren't working.
    from engine.config import LEECH_LAPSES
    lapses = dao.get_lapses(item.concept_id)
    leech = lapses >= LEECH_LAPSES
    if leech:
        print(f"   ⚠️  leech — missed {lapses}× before. Slow down; re-read first.")
    # Cold start: not yet learned (never seen / never correct / low mastery) — give
    # the explanation up front so it isn't a blind guess.
    from engine.analytics.readiness import concept_mastery
    from engine.config import COLD_START_MASTERY
    cold = concept_mastery(item.concept_id) < COLD_START_MASTERY
    if (cold or leech) and item.theory:
        print(f"   📖 Start here: {item.theory}")
    note = dao.get_mnemonic(item.concept_id)
    if note:
        print(f"   📝 your note: {note}")
    for letter, choice in zip(LETTERS, item.choices, strict=False):
        print(f"   {letter}) {choice}")

    start = time.monotonic()
    raw = _prompt("Your answer: " if typed else "Your answer (letter): ")
    elapsed_ms = int((time.monotonic() - start) * 1000)

    outcome = loop.settle(turn.item_id, raw, elapsed_ms)
    verdict = "✓ Correct" if outcome.correct else f"✗ Incorrect — answer: {item.correct}"
    print(f"{verdict}   [{GRADE_LABEL[outcome.grade]}, {elapsed_ms / 1000:.1f}s]")
    for step in item.explain:
        print(f"   · {step}")
    if outcome.why_wrong:
        print(f"   ✗ {outcome.why_wrong}")
    # Surface the concept explanation right or wrong (skip if it was already shown
    # as the up-front cold-start / leech intro).
    if item.theory and not cold and not leech:
        print(f"   📖 {item.theory}")
    for record in outcome.records:
        print(f"   {record}")
    if outcome.next_review_days is not None:
        print(f"   ↩️  back in {outcome.next_review_days} day(s)")

    # A leech needs a reformulation, not more reps — ask for the hint even after a
    # correct answer while none is saved.
    if outcome.ask_mnemonic:
        hint = _prompt("Add a hint for next time (Enter to skip): ").strip()
        if hint:
            dao.save_mnemonic(item.concept_id, hint)
    return outcome


def _print_run_framing(outcome: service.AnswerOutcome, prev_tier: str) -> str:
    """Print the combo-break / reward / tier lines for one answer; return the tier.

    The tier prints only when it changes, so the caller threads the previous tier
    through and takes back the new one.
    """
    if outcome.combo_break:
        print(f"   {outcome.combo_break}")
    if outcome.reward:
        print(f"   {outcome.reward}")
    if outcome.combo and outcome.combo != prev_tier:
        print(f"   {outcome.combo} ×{outcome.streak}")
    return outcome.combo


def _fatigue_note(recent: list[bool], warned: bool) -> bool:
    """Print a break suggestion once when recent accuracy craters; return new flag."""
    from engine.config import FATIGUE_THRESHOLD, FATIGUE_WINDOW
    w = recent[-FATIGUE_WINDOW:]
    if not warned and len(w) >= FATIGUE_WINDOW and sum(w) / len(w) < FATIGUE_THRESHOLD:
        print("   😮‍💨 accuracy dipping — a short break may help retention.")
        return True
    return warned


def run(subject: str, n: int) -> None:
    if subject not in SUBJECTS:
        print(f"Unknown subject '{subject}'. Choose from: {', '.join(SUBJECTS)}")
        return
    load_subject(subject)
    info = SUBJECTS[subject]
    loop = StudyLoop.start(subject, n)
    print(f"\n=== {info.title} ===\n{info.blurb}")
    _print_hud()

    prev_tier = ""
    fatigued = False
    while True:
        step = loop.next()
        if isinstance(step, Done):
            break
        tag = {"new": "NEW", "review": "review", "retry": "RETRY"}[step.item.reason]
        print(f"\n--- item {loop.index}/{n}  ({tag}) ---", end="")
        outcome = _run_item(loop, step)
        fatigued = _fatigue_note(loop.recent, fatigued)
        prev_tier = _print_run_framing(outcome, prev_tier)

    _print_summary(
        f"{info.title} — session done", step.summary["answered"], step.summary["correct"]
    )


def run_global(n: int) -> None:
    """Interleaved spaced repetition across every subject — the unified default.

    Pulls the weakest due item from any subject, down-weighting the subject just
    studied so the queue interleaves. Opens and closes with confidence builders,
    and slips one in after two misses in a row to pace toward ~85% success.
    """
    load_all()
    loop = StudyLoop.start("global", n)
    print("\n=== StudyEngine — Global Interleaved Session ===")
    print("Weakest-first across all subjects, interleaved. Start optimizing.")
    _print_hud()
    if loop.dkt_active:
        print("DKT active — selection driven by the trained global model.")

    prev_tier = ""
    fatigued = False
    while True:
        step = loop.next()
        if isinstance(step, Done):
            break
        item = step.item
        if item.reason == "retry":
            builder = " · re-test (you missed this)"
        elif step.mode == "confidence" and item.reason == "review":
            builder = " · confidence builder"
        else:
            builder = ""
        label = SUBJECTS[item.subject].title.split("—")[0].strip()
        print(f"\n--- item {loop.index}/{n}  [{label}]{builder} ---", end="")
        outcome = _run_item(loop, step)
        fatigued = _fatigue_note(loop.recent, fatigued)
        prev_tier = _print_run_framing(outcome, prev_tier)

    _print_summary(
        f"Global session — {step.summary['subjects']} subject(s)",
        step.summary["answered"], step.summary["correct"],
    )
    print("Run `python -m engine.cli.dashboard` to see your map light up.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Study with FSRS scheduling.")
    parser.add_argument("--subject", choices=list(SUBJECTS), default=None,
                        help="study one subject (focus/cram mode)")
    parser.add_argument("--all", action="store_true",
                        help="interleaved global session across all subjects (default)")
    parser.add_argument("--n", type=int, default=12, help="items this session")
    args = parser.parse_args()
    if args.subject and not args.all:
        run(args.subject, args.n)
    else:
        run_global(args.n)


if __name__ == "__main__":
    main()
