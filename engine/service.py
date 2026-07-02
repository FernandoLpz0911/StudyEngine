"""Shared study-item service: build a servable item and grade an answer.

Used by both the CLI and the HTTP API so problem generation, recall presentation,
and objective grading have one implementation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

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
    theory: str | None = None
    explanations: dict = field(default_factory=dict)
    tolerance: float = 1e-3


def _serve_typed(concept: Concept) -> bool:
    """Whether a generator concept has outgrown multiple choice.

    Recognition is easier than recall: once mastery is high the four options give
    the answer away, so the item switches to a typed free response.
    """
    from engine import settings
    from engine.analytics.readiness import concept_mastery
    return concept_mastery(concept.id) >= settings.get_float("typed_answer_mastery")


def build_item(concept: Concept, rng: np.random.Generator, reason: str = "") -> StudyItem:
    """Produce a servable item from a concept (generator problem or recall card)."""
    if concept.mode == "generator" and concept.generator:
        spec = concept.generator
        ask = pick_ask(spec["params"]["ask"])
        seed = random_seed()
        problem = generate(spec["kind"], ask, spec["params"], seed)
        choices = [] if _serve_typed(concept) else (problem.choices or [])
        return StudyItem(
            concept.id, concept.name, concept.subject, reason,
            f"{spec['kind']}:{ask}", problem.statement, choices,
            f"{problem.correct_answer:.3f}",
            worked_solution(spec["kind"], ask, problem.params), seed, problem.params,
            theory=concept.theory_md, tolerance=problem.tolerance,
        )
    question = as_question(concept, rng)
    return StudyItem(
        concept.id, concept.name, concept.subject, reason, "recall",
        question.question, question.choices, question.correct,
        [f"Correct answer: {question.correct}"], 0, {},
        theory=concept.theory_md, explanations=concept.card_explanations,
    )


def explanation_for(answer: str, item: StudyItem) -> str:
    """Why the learner's wrong choice is wrong, if the author supplied one."""
    if not item.explanations:
        return ""
    answer = answer.strip()
    if answer.lower() in LETTERS and LETTERS.index(answer.lower()) < len(item.choices):
        answer = item.choices[LETTERS.index(answer.lower())]
    return item.explanations.get(answer, "")


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
    tolerance = item.tolerance
    if not item.choices:
        # Typed free response: the key is rounded to 3 decimals, and the learner may
        # round differently, so widen to a relative tolerance around the true value.
        from engine.config import TYPED_REL_TOLERANCE
        try:
            tolerance = max(tolerance, abs(float(item.correct)) * TYPED_REL_TOLERANCE)
        except ValueError:
            pass
    return grade_answer(answer, item.correct, tolerance)


def grade(answer: str, elapsed_ms: int, item: StudyItem) -> tuple[bool, int]:
    """Return (is_correct, derived FSRS grade) for an answer — purely data-based.

    Recall cards and multi-step generator problems have different natural response
    times, so each mode grades speed against its own thresholds.
    """
    from engine.config import (
        GRADE_FAST_MS,
        GRADE_FAST_MS_GEN,
        GRADE_SLOW_MS,
        GRADE_SLOW_MS_GEN,
    )
    correct = is_correct(answer, item)
    if item.kind == "recall":
        fast, slow = GRADE_FAST_MS, GRADE_SLOW_MS
    else:
        fast, slow = GRADE_FAST_MS_GEN, GRADE_SLOW_MS_GEN
    return correct, derive_grade(correct, elapsed_ms, fast, slow)
