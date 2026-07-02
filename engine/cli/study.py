"""Interactive study loop: python -m engine.cli.study --subject diffeq [--n 10].

Every item is objectively auto-graded — generator problems against their computed
answer, recall concepts against the correct multiple-choice option. There is no
self-rating: correctness plus response time alone derive the FSRS grade. Progress
persists in the SQLite database between runs.
"""
from __future__ import annotations

import argparse
import time

import numpy as np

import engine.subjects  # noqa: F401  (registers the problem generators)
from engine import service, stats
from engine.config import RETRY_GAP
from engine.db import dao
from engine.db.seed import load_all, load_subject
from engine.engagement import combo_label, reward_message
from engine.scheduler import policy, store
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


def _days_until(due) -> int | None:
    """Whole days until a card's next review, for the 'back in N days' open loop."""
    if due is None:
        return None
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    d = due if due.tzinfo else due.replace(tzinfo=UTC)
    return max(0, (d - now).days)


def _pop_retry(retry: list[tuple[str, int]], index: int, force: bool):
    """Next queued missed concept whose spacing gap elapsed, or None (errorful retry)."""
    for i, (cid, ready) in enumerate(retry):
        if force or index >= ready:
            concept = dao.get_concept(cid)
            retry.pop(i)
            if concept is not None:
                return concept
    return None


def _run_item(concept, session_id: int, rng: np.random.Generator, reason: str = "") -> bool:
    item = service.build_item(concept, rng, reason)
    item_id = service.log_item_shown(session_id, item)

    typed = not item.choices
    print(f"\n[{concept.name}]  {item.question}")
    if typed:
        print("   ✍️  no options this time — you know this one; type the value")
    # Leech: repeatedly forgotten — slow down and re-read; more raw reps aren't working.
    from engine.config import LEECH_LAPSES
    lapses = dao.get_lapses(concept.id)
    leech = lapses >= LEECH_LAPSES
    if leech:
        print(f"   ⚠️  leech — missed {lapses}× before. Slow down; re-read first.")
    # Cold start: not yet learned (never seen / never correct / low mastery) — give
    # the explanation up front so it isn't a blind guess.
    from engine.analytics.readiness import concept_mastery
    from engine.config import COLD_START_MASTERY
    cold = concept_mastery(concept.id) < COLD_START_MASTERY
    if (cold or leech) and item.theory:
        print(f"   📖 Start here: {item.theory}")
    note = dao.get_mnemonic(concept.id)
    if note:
        print(f"   📝 your note: {note}")
    for letter, choice in zip(LETTERS, item.choices, strict=False):
        print(f"   {letter}) {choice}")

    start = time.monotonic()
    raw = _prompt("Your answer: " if typed else "Your answer (letter): ")
    elapsed_ms = int((time.monotonic() - start) * 1000)

    correct, grade = service.grade(raw, elapsed_ms, item)
    verdict = "✓ Correct" if correct else f"✗ Incorrect — answer: {item.correct}"
    print(f"{verdict}   [{GRADE_LABEL[grade]}, {elapsed_ms / 1000:.1f}s]")
    for step in item.explain:
        print(f"   · {step}")
    if not correct:
        why = service.explanation_for(raw, item)
        if why:
            print(f"   ✗ {why}")
    # Surface the concept explanation right or wrong (skip if it was already shown
    # as the up-front cold-start / leech intro).
    if item.theory and not cold and not leech:
        print(f"   📖 {item.theory}")

    dao.log_answered(item_id, raw or None, correct, grade, elapsed_ms)
    if correct:
        dao.remove_pending_retry(concept.id)  # debt paid, if any
    else:
        dao.add_pending_retry(concept.id)  # owed a re-test even across sessions
    new_state = store.apply_rating(store.get_or_create(concept.id), grade)
    store.save(new_state)
    days = _days_until(new_state.due)
    if days is not None:
        print(f"   ↩️  back in {days} day(s)")

    # A leech needs a reformulation, not more reps — ask for the hint even after a
    # correct answer while none is saved.
    if note is None and (not correct or leech):
        hint = _prompt("Add a hint for next time (Enter to skip): ").strip()
        if hint:
            dao.save_mnemonic(concept.id, hint)
    return correct


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
    session_id = dao.create_session(subject)
    info = SUBJECTS[subject]
    rng = np.random.default_rng()
    print(f"\n=== {info.title} ===\n{info.blurb}")
    _print_hud()

    streak = 0
    answered = correct_count = 0
    prev_tier = ""
    # Missed concepts from earlier sessions are owed a re-test — front-load them.
    subject_pending = {c.id for c in dao.get_concepts(subject)}
    retry: list[tuple[str, int]] = [
        (cid, 0) for cid in dao.pending_retries() if cid in subject_pending
    ]
    recent: list[bool] = []
    fatigued = False
    for i in range(n):
        concept = _pop_retry(retry, i, force=False)
        reason = "retry"
        if concept is None:
            selection = policy.select_next(subject)
            if selection is None:
                print("\nNothing due right now — all caught up. ✓")
                break
            concept, reason = selection.concept, selection.reason
        tag = {"new": "NEW", "review": "review", "retry": "RETRY"}[reason]
        print(f"\n--- item {i + 1}/{n}  ({tag}) ---", end="")
        correct = _run_item(concept, session_id, rng, reason)
        answered += 1
        correct_count += correct
        recent.append(correct)
        fatigued = _fatigue_note(recent, fatigued)
        if not correct and reason != "retry":
            retry.append((concept.id, i + RETRY_GAP))
        streak = streak + 1 if correct else 0
        if msg := reward_message(correct, streak, rng):
            print(f"   {msg}")
        tier = combo_label(streak)
        if tier and tier != prev_tier:
            print(f"   {tier} ×{streak}")
        prev_tier = tier

    dao.close_session(session_id)
    _print_summary(f"{info.title} — session done", answered, correct_count)


def run_global(n: int) -> None:
    """Interleaved spaced repetition across every subject — the unified default.

    Pulls the weakest due item from any subject, down-weighting the subject just
    studied so the queue interleaves. Opens and closes with confidence builders,
    and slips one in after two misses in a row to pace toward ~85% success.
    """
    from engine.config import GLOBAL_COOLDOWN, GLOBAL_WARMUP

    load_all()
    session_id = dao.create_session("global")
    rng = np.random.default_rng()
    subjects = list(SUBJECTS)
    print("\n=== StudyEngine — Global Interleaved Session ===")
    print("Weakest-first across all subjects, interleaved. Start optimizing.")
    _print_hud()

    from engine.tracing import infer
    dkt_active = infer.dkt_is_active()
    p_correct = (
        infer.predict(dao.get_interaction_history_timed()) if dkt_active else None
    )
    if dkt_active:
        print("DKT active — selection driven by the trained global model.")

    last_subject: str | None = None
    recent: list[bool] = []
    touched: set[str] = set()
    streak = 0
    prev_tier = ""
    retry: list[tuple[str, int]] = [(cid, 0) for cid in dao.pending_retries()]
    fatigued = False
    for i in range(n):
        if dkt_active and i > 0 and i % 5 == 0:
            p_correct = infer.predict(dao.get_interaction_history_timed())
        concept = _pop_retry(retry, i, force=False)
        reason = "retry"
        builder = " · re-test (you missed this)"
        if concept is None:
            warm_or_cool = i < GLOBAL_WARMUP or i >= n - GLOBAL_COOLDOWN
            stalling = recent[-2:] == [False, False]
            mode = "confidence" if (warm_or_cool or stalling) else "weak"
            selection = policy.select_global(
                subjects, avoid_subject=last_subject, mode=mode, p_correct=p_correct
            )
            if selection is None:
                print("\nNothing available yet — study a single subject to open new concepts.")
                break
            concept, reason = selection.concept, selection.reason
            is_builder = mode == "confidence" and reason == "review"
            builder = " · confidence builder" if is_builder else ""
        label = SUBJECTS[concept.subject].title.split("—")[0].strip()
        print(f"\n--- item {i + 1}/{n}  [{label}]{builder} ---", end="")
        correct = _run_item(concept, session_id, rng, reason)
        if not correct and reason != "retry":
            retry.append((concept.id, i + RETRY_GAP))
        recent.append(correct)
        fatigued = _fatigue_note(recent, fatigued)
        streak = streak + 1 if correct else 0
        if msg := reward_message(correct, streak, rng):
            print(f"   {msg}")
        tier = combo_label(streak)
        if tier and tier != prev_tier:
            print(f"   {tier} ×{streak}")
        prev_tier = tier
        last_subject = concept.subject
        touched.add(concept.subject)

    dao.close_session(session_id)
    _print_summary(
        f"Global session — {len(touched)} subject(s)", len(recent), sum(recent)
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
