"""Interactive study loop: python -m engine.cli.study --subject diffeq [--n 10].

Every item is objectively auto-graded — generator problems against their computed
answer, recall concepts against the correct multiple-choice option. There is no
self-rating: correctness plus response time alone derive the FSRS grade. Progress
persists in the SQLite database between runs.
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass

import numpy as np

import engine.subjects  # noqa: F401  (registers the problem generators)
from engine.db import dao
from engine.db.seed import load_all, load_subject
from engine.feedback.solve import worked_solution
from engine.generation.base import generate, pick_ask, random_seed
from engine.grading import derive_grade, grade_answer
from engine.recall.cards import as_question
from engine.scheduler import policy, store
from engine.subjects import SUBJECTS

LETTERS = ["a", "b", "c", "d"]
GRADE_LABEL = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}


@dataclass
class StudyItem:
    kind: str
    question: str
    choices: list[str]
    correct: str
    explain: list[str]
    seed: int
    params: dict


def _build_item(concept, rng: np.random.Generator) -> StudyItem:
    if concept.mode == "generator" and concept.generator:
        spec = concept.generator
        ask = pick_ask(spec["params"]["ask"])
        seed = random_seed()
        problem = generate(spec["kind"], ask, spec["params"], seed)
        correct = f"{problem.correct_answer:.3f}"
        explain = worked_solution(spec["kind"], ask, problem.params)
        return StudyItem(
            f"{spec['kind']}:{ask}", problem.statement, problem.choices or [],
            correct, explain, seed, problem.params,
        )
    question = as_question(concept, rng)
    return StudyItem(
        "recall", question.question, question.choices, question.correct,
        [f"Correct answer: {question.correct}"], 0, {},
    )


def _is_correct(raw: str, item: StudyItem) -> bool:
    raw = raw.strip().lower()
    if raw in LETTERS and LETTERS.index(raw) < len(item.choices):
        return item.choices[LETTERS.index(raw)] == item.correct
    return grade_answer(raw, item.correct)


def _prompt(text: str) -> str:
    try:
        return input(text)
    except EOFError:
        return ""


def _run_item(concept, session_id: int, rng: np.random.Generator) -> bool:
    item = _build_item(concept, rng)
    item_id = dao.log_shown(
        session_id, concept.id, concept.subject, item.kind,
        seed=item.seed, params_json=json.dumps(item.params), correct_answer=item.correct,
    )

    print(f"\n[{concept.name}]  {item.question}")
    for letter, choice in zip(LETTERS, item.choices, strict=False):
        print(f"   {letter}) {choice}")

    start = time.monotonic()
    raw = _prompt("Your answer (letter): ")
    elapsed_ms = int((time.monotonic() - start) * 1000)

    is_correct = _is_correct(raw, item)
    grade = derive_grade(is_correct, elapsed_ms)
    verdict = "✓ Correct" if is_correct else f"✗ Incorrect — answer: {item.correct}"
    print(f"{verdict}   [{GRADE_LABEL[grade]}, {elapsed_ms / 1000:.1f}s]")
    for step in item.explain:
        print(f"   · {step}")

    dao.log_answered(item_id, raw or None, is_correct, grade, elapsed_ms)
    store.save(store.apply_rating(store.get_or_create(concept.id), grade))
    return is_correct


def run(subject: str, n: int) -> None:
    if subject not in SUBJECTS:
        print(f"Unknown subject '{subject}'. Choose from: {', '.join(SUBJECTS)}")
        return
    load_subject(subject)
    session_id = dao.create_session(subject)
    info = SUBJECTS[subject]
    rng = np.random.default_rng()
    print(f"\n=== {info.title} ===\n{info.blurb}")

    for i in range(n):
        selection = policy.select_next(subject)
        if selection is None:
            print("\nNothing due right now — all caught up. ✓")
            break
        tag = "NEW" if selection.reason == "new" else "review"
        print(f"\n--- item {i + 1}/{n}  ({tag}) ---", end="")
        _run_item(selection.concept, session_id, rng)

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
        recent.append(_run_item(concept, session_id, rng))
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
