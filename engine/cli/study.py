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
from engine import service
from engine.db import dao
from engine.db.seed import load_all, load_subject
from engine.engagement import reward_message
from engine.scheduler import policy, store
from engine.service import GRADE_LABEL, LETTERS
from engine.subjects import SUBJECTS


def _prompt(text: str) -> str:
    try:
        return input(text)
    except EOFError:
        return ""


def _run_item(concept, session_id: int, rng: np.random.Generator) -> bool:
    item = service.build_item(concept, rng)
    item_id = service.log_item_shown(session_id, item)

    print(f"\n[{concept.name}]  {item.question}")
    note = dao.get_mnemonic(concept.id)
    if note:
        print(f"   📝 your note: {note}")
    for letter, choice in zip(LETTERS, item.choices, strict=False):
        print(f"   {letter}) {choice}")

    start = time.monotonic()
    raw = _prompt("Your answer (letter): ")
    elapsed_ms = int((time.monotonic() - start) * 1000)

    correct, grade = service.grade(raw, elapsed_ms, item)
    verdict = "✓ Correct" if correct else f"✗ Incorrect — answer: {item.correct}"
    print(f"{verdict}   [{GRADE_LABEL[grade]}, {elapsed_ms / 1000:.1f}s]")
    for step in item.explain:
        print(f"   · {step}")

    dao.log_answered(item_id, raw or None, correct, grade, elapsed_ms)
    store.save(store.apply_rating(store.get_or_create(concept.id), grade))

    if not correct and note is None:
        hint = _prompt("Add a hint for next time (Enter to skip): ").strip()
        if hint:
            dao.save_mnemonic(concept.id, hint)
    return correct


def run(subject: str, n: int) -> None:
    if subject not in SUBJECTS:
        print(f"Unknown subject '{subject}'. Choose from: {', '.join(SUBJECTS)}")
        return
    load_subject(subject)
    session_id = dao.create_session(subject)
    info = SUBJECTS[subject]
    rng = np.random.default_rng()
    print(f"\n=== {info.title} ===\n{info.blurb}")

    streak = 0
    for i in range(n):
        selection = policy.select_next(subject)
        if selection is None:
            print("\nNothing due right now — all caught up. ✓")
            break
        tag = "NEW" if selection.reason == "new" else "review"
        print(f"\n--- item {i + 1}/{n}  ({tag}) ---", end="")
        correct = _run_item(selection.concept, session_id, rng)
        streak = streak + 1 if correct else 0
        if msg := reward_message(correct, streak, rng):
            print(f"   {msg}")

    dao.close_session(session_id)
    stats = dao.subject_stats(subject)
    print(
        f"\nSession done. {info.title}: {stats['answered']} answered, "
        f"{int(stats['accuracy'] * 100)}% correct (lifetime)."
    )


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
    for i in range(n):
        if dkt_active and i > 0 and i % 5 == 0:
            p_correct = infer.predict(dao.get_interaction_history_timed())
        warm_or_cool = i < GLOBAL_WARMUP or i >= n - GLOBAL_COOLDOWN
        stalling = recent[-2:] == [False, False]
        mode = "confidence" if (warm_or_cool or stalling) else "weak"
        selection = policy.select_global(
            subjects, avoid_subject=last_subject, mode=mode, p_correct=p_correct
        )
        if selection is None:
            print("\nNothing available yet — study a single subject to open new concepts.")
            break
        concept = selection.concept
        label = SUBJECTS[concept.subject].title.split("—")[0].strip()
        is_builder = mode == "confidence" and selection.reason == "review"
        builder = " · confidence builder" if is_builder else ""
        print(f"\n--- item {i + 1}/{n}  [{label}]{builder} ---", end="")
        correct = _run_item(concept, session_id, rng)
        recent.append(correct)
        streak = streak + 1 if correct else 0
        if msg := reward_message(correct, streak, rng):
            print(f"   {msg}")
        last_subject = concept.subject
        touched.add(concept.subject)

    dao.close_session(session_id)
    print(f"\nSession done — {len(recent)} items across {len(touched)} subject(s).")
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
