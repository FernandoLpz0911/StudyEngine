"""Shared study-item service: build a servable item and grade an answer.

Used by both the CLI and the HTTP API so problem generation, recall presentation,
and objective grading have one implementation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from engine.db import dao
from engine.db.dao import Concept
from engine.feedback.solve import worked_solution
from engine.generation.base import generate, pick_ask, random_seed
from engine.grading import derive_grade, grade_answer
from engine.recall.cards import as_question

LETTERS = ["a", "b", "c", "d"]
GRADE_LABEL = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}


@dataclass
class StudyItem:
    concept_id: str
    concept_name: str
    subject: str
    reason: str
    kind: str
    question: str
    choices: list[str]
    correct: str
    explain: list[str]
    seed: int
    params: dict


def build_item(concept: Concept, rng: np.random.Generator, reason: str = "") -> StudyItem:
    """Produce a servable item from a concept (generator problem or recall card)."""
    if concept.mode == "generator" and concept.generator:
        spec = concept.generator
        ask = pick_ask(spec["params"]["ask"])
        seed = random_seed()
        problem = generate(spec["kind"], ask, spec["params"], seed)
        return StudyItem(
            concept.id, concept.name, concept.subject, reason,
            f"{spec['kind']}:{ask}", problem.statement, problem.choices or [],
            f"{problem.correct_answer:.3f}",
            worked_solution(spec["kind"], ask, problem.params), seed, problem.params,
        )
    question = as_question(concept, rng)
    return StudyItem(
        concept.id, concept.name, concept.subject, reason, "recall",
        question.question, question.choices, question.correct,
        [f"Correct answer: {question.correct}"], 0, {},
    )


def log_item_shown(session_id: int, item: StudyItem) -> int:
    """Persist that an item was served; return the interaction id."""
    return dao.log_shown(
        session_id, item.concept_id, item.subject, item.kind,
        seed=item.seed, params_json=json.dumps(item.params), correct_answer=item.correct,
    )


def is_correct(answer: str, item: StudyItem) -> bool:
    """Grade a chosen answer — a letter, the option text, or a typed numeric value."""
    answer = answer.strip()
    if answer.lower() in LETTERS and LETTERS.index(answer.lower()) < len(item.choices):
        return item.choices[LETTERS.index(answer.lower())] == item.correct
    return grade_answer(answer, item.correct)


def grade(answer: str, elapsed_ms: int, item: StudyItem) -> tuple[bool, int]:
    """Return (is_correct, derived FSRS grade) for an answer — purely data-based."""
    correct = is_correct(answer, item)
    return correct, derive_grade(correct, elapsed_ms)
