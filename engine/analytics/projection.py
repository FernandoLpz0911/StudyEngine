"""What the learner would score if they sat the exam today.

Readiness used to be a count of concepts over a mastery threshold. That number is
not calibrated to anything the exam decides: a plan implying roughly 88% accuracy
per concept reported as "6 of 34 mastered", which reads as a failure and is a
comfortable pass. Worse, optimising it recommended dropping ten low-weight
concepts — a change that a projected score shows *costs* about a mark, because a
dropped concept still appears on the paper and is then guessed (ADR-0012).

So readiness is a projected raw score against the pass mark. Mastery keeps its
job as the per-concept signal behind drills and resting; it is no longer the
headline.

The model is deliberately conservative in two places and honest in a third:

- `accuracy × retention`, *not* mastery. Mastery multiplies in a rep-confidence
  term, which measures how much evidence there is rather than how good the
  learner is; folding it into the estimate marks down a concept for being
  lightly practised and then again for being uncertain.
- practice is free response well below the mastery at which the real exam would
  still be offering five options, so measured accuracy understates exam accuracy.
- the guessing floor is credited, because a blank guess on five options really
  does score one in five.

The arithmetic is pure; only `projected_score` reads the database.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from engine.config import (
    EXAM_GUESS_P,
    EXAM_PASS_MARK,
    EXAM_QUESTIONS,
    EXAM_TARGET_MARGIN,
)


def p_skill(accuracy: float | None, retention: float) -> float:
    """Probability of solving a question on this concept unaided.

    None accuracy means never answered, which is zero skill rather than an
    unknown to be guessed at generously.
    """
    if accuracy is None:
        return 0.0
    return max(0.0, min(1.0, accuracy * retention))


def p_exam(skill: float, guess: float = EXAM_GUESS_P) -> float:
    """Probability of *marking* a question right, skill or luck.

    Even total ignorance scores the guessing floor on a multiple-choice paper, so
    the floor is what an unstudied concept is worth — not zero.
    """
    skill = max(0.0, min(1.0, skill))
    return skill + (1.0 - skill) * guess


def concept_p_exam(concept_id: str, now=None) -> float:
    """One concept's chance of being marked right, on the model above.

    Shared by the projection and by drill targeting so the number the readout
    reports and the number that decides what gets practised cannot drift apart.
    """
    from datetime import UTC, datetime

    from engine.analytics.readiness import _retention_now
    from engine.config import MASTERY_ACCURACY_WINDOW
    from engine.db import dao
    from engine.scheduler import store

    now = now or datetime.now(UTC)
    state = store.get_or_create(concept_id)
    if state.reps == 0:
        return p_exam(0.0)
    accuracy = dao.get_concept_accuracy(concept_id, window=MASTERY_ACCURACY_WINDOW)
    return p_exam(p_skill(accuracy, _retention_now(state, now)))


@dataclass(frozen=True)
class Projection:
    """The score the learner would be expected to earn today."""

    subject: str
    score: float
    questions: int
    pass_mark: int
    target: int
    margin: float
    passing: bool
    ready: bool
    weakest: list[tuple[str, float]]

    def as_dict(self) -> dict:
        return asdict(self)


def projected_score(subject: str) -> Projection:
    """Expected raw score, from each concept's measured accuracy and retention.

    Every concept in the subject contributes, whether or not it has been studied:
    the exam asks about all of them, and an unstudied one is answered at the
    guessing floor. That is what makes the number comparable across plans that
    cover different amounts of the syllabus.
    """
    from datetime import UTC, datetime

    from engine.db import dao

    now = datetime.now(UTC)
    concepts = dao.get_concepts(subject)
    total_weight = sum(c.exam_weight for c in concepts) or 1

    score = 0.0
    per_concept: list[tuple[str, float]] = []
    for concept in concepts:
        marked = concept_p_exam(concept.id, now)
        # A concept's share of the paper is its share of the exam weight.
        score += marked * EXAM_QUESTIONS * concept.exam_weight / total_weight
        per_concept.append((concept.name, marked))

    per_concept.sort(key=lambda row: row[1])
    target = EXAM_PASS_MARK + EXAM_TARGET_MARGIN
    return Projection(
        subject=subject,
        score=round(score, 1),
        questions=EXAM_QUESTIONS,
        pass_mark=EXAM_PASS_MARK,
        target=target,
        margin=round(score - EXAM_PASS_MARK, 1),
        passing=score >= EXAM_PASS_MARK,
        ready=score >= target,
        weakest=[(name, round(p, 2)) for name, p in per_concept[:5]],
    )
