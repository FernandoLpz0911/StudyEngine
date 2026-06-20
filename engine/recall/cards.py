"""Recall mode: present a concept as a flashcard, self-graded into FSRS.

Recall concepts (proofs, econ, conceptual DB topics) have no closed-form answer,
so there is nothing to auto-grade. The learner sees the prompt, recalls, reveals
the answer, then rates honestly — the rating feeds the same FSRS scheduler that
generator subjects use.
"""
from __future__ import annotations

from dataclasses import dataclass

from engine.db.dao import Concept

# Self-rating → FSRS Rating value (1 Again, 2 Hard, 3 Good, 4 Easy).
RECALL_GRADES: dict[str, int] = {"again": 1, "hard": 2, "good": 3, "easy": 4}


@dataclass
class Flashcard:
    concept_id: str
    front: str
    back: str


def as_flashcard(concept: Concept) -> Flashcard:
    """Build a flashcard from a recall concept, falling back to its name/theory."""
    front = concept.card_front or f"Explain: {concept.name}"
    back = concept.card_back or (concept.theory_md or "(no answer recorded)")
    return Flashcard(concept_id=concept.id, front=front, back=back)
