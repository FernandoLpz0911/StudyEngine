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
from engine.db.seed import load_subject
from engine.generation.base import generate, pick_ask, random_seed
from engine.grading import derive_grade, grade_answer
from engine.recall.cards import as_question
from engine.scheduler import policy, store
from engine.subjects import SUBJECTS
from engine.subjects.diffeq.solve import solve as diffeq_solve

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
        explain = diffeq_solve(spec["kind"], ask, problem.params).steps
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


def _run_item(concept, session_id: int, rng: np.random.Generator) -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Study one subject with FSRS scheduling.")
    parser.add_argument("--subject", required=True, choices=list(SUBJECTS))
    parser.add_argument("--n", type=int, default=10, help="number of items this session")
    args = parser.parse_args()
    run(args.subject, args.n)


if __name__ == "__main__":
    main()
