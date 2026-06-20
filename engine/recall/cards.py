"""Recall mode as objective multiple-choice — no self-rating.

A recall concept stores a question, one correct answer, and distractors. It is
served as a shuffled multiple-choice item and graded the same way as a generator
problem: the chosen option either equals the correct one or it does not.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.db.dao import Concept


@dataclass
class RecallQuestion:
    concept_id: str
    question: str
    choices: list[str]
    correct: str


def as_question(concept: Concept, rng: np.random.Generator) -> RecallQuestion:
    """Build a shuffled multiple-choice item from a recall concept."""
    answer = concept.card_answer or concept.name
    options = [answer, *concept.card_distractors]
    order = rng.permutation(len(options))
    choices = [options[i] for i in order]
    question = concept.card_question or f"Recall: {concept.name}"
    return RecallQuestion(concept.id, question, choices, answer)
