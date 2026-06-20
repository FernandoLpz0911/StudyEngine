"""Interactive study loop: python -m engine.cli.study --subject diffeq [--n 10].

Drives the shared FSRS scheduler for one subject. Generator concepts serve an
auto-graded problem with a worked solution; recall concepts serve a self-graded
flashcard. Progress persists in the SQLite database between runs.
"""
from __future__ import annotations

import argparse

import engine.subjects  # noqa: F401  (registers the problem generators)
from engine.db import dao
from engine.db.seed import load_subject
from engine.generation.base import generate, pick_ask, random_seed
from engine.grading import grade_answer
from engine.recall.cards import as_flashcard
from engine.scheduler import policy, store
from engine.subjects import SUBJECTS
from engine.subjects.diffeq.solve import solve as diffeq_solve

LETTERS = ["a", "b", "c", "d"]


def _prompt(text: str) -> str:
    try:
        return input(text)
    except EOFError:
        return "quit"


def _serve_generator(concept, session_id: int) -> None:
    spec = concept.generator
    ask = pick_ask(spec["params"]["ask"])
    seed = random_seed()
    problem = generate(spec["kind"], ask, spec["params"], seed)
    correct = f"{problem.correct_answer:.3f}"

    item_id = dao.log_shown(
        session_id, concept.id, concept.subject, f"{spec['kind']}:{ask}",
        seed=seed, params_json=_json(problem.params), correct_answer=correct,
    )

    print(f"\n[{concept.name}]  {problem.statement}")
    for letter, choice in zip(LETTERS, problem.choices or [], strict=False):
        print(f"   {letter}) {choice}")
    raw = _prompt("Your answer (letter or value, Enter to reveal): ").strip().lower()

    chosen = problem.choices[LETTERS.index(raw)] if raw in LETTERS and problem.choices else raw
    is_correct = grade_answer(chosen, correct) if chosen else False

    print("✓ Correct!" if is_correct else f"✗ Answer: {correct}")
    for step in diffeq_solve(spec["kind"], ask, problem.params).steps:
        print(f"   · {step}")

    dao.log_answered(item_id, chosen or None, is_correct, grade=3 if is_correct else 1)
    _reschedule(concept.id, 3 if is_correct else 1)


def _serve_recall(concept, session_id: int) -> None:
    card = as_flashcard(concept)
    item_id = dao.log_shown(session_id, concept.id, concept.subject, "recall")
    print(f"\n[{concept.name}]  {card.front}")
    _prompt("(press Enter to reveal) ")
    print(f"   → {card.back}")
    raw = _prompt("Rate recall — (a)gain (h)ard (g)ood (e)asy: ").strip().lower()
    grade = {"a": 1, "h": 2, "g": 3, "e": 4}.get(raw[:1], 3)
    dao.log_answered(item_id, None, None, grade=grade)
    _reschedule(concept.id, grade)


def _reschedule(concept_id: str, grade: int) -> None:
    store.save(store.apply_rating(store.get_or_create(concept_id), grade))


def _json(params: dict) -> str:
    import json
    return json.dumps(params)


def run(subject: str, n: int) -> None:
    if subject not in SUBJECTS:
        print(f"Unknown subject '{subject}'. Choose from: {', '.join(SUBJECTS)}")
        return
    load_subject(subject)
    session_id = dao.create_session(subject)
    info = SUBJECTS[subject]
    print(f"\n=== {info.title} ===\n{info.blurb}")

    for i in range(n):
        selection = policy.select_next(subject)
        if selection is None:
            print("\nNothing due right now — all caught up. ✓")
            break
        tag = "NEW" if selection.reason == "new" else "review"
        print(f"\n--- item {i + 1}/{n}  ({tag}) ---", end="")
        concept = selection.concept
        if concept.mode == "generator" and concept.generator:
            _serve_generator(concept, session_id)
        else:
            _serve_recall(concept, session_id)

    dao.close_session(session_id)
    stats = dao.subject_stats(subject)
    print(
        f"\nSession done. {info.title}: {stats['answered']} answered, "
        f"{int(stats['accuracy'] * 100)}% correct (lifetime)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Study one subject with FSRS scheduling.")
    parser.add_argument("--subject", required=True, choices=list(SUBJECTS))
    parser.add_argument("--n", type=int, default=10, help="number of items this session")
    args = parser.parse_args()
    run(args.subject, args.n)


if __name__ == "__main__":
    main()
