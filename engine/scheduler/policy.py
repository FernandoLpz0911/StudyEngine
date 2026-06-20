"""Next-concept selection for a subject: overdue reviews first, then new frontier."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from engine.db import dao
from engine.db.dao import Concept
from engine.scheduler import store
from engine.scheduler.fsrs_core import retrievability
from engine.scheduler.store import CardState


@dataclass
class Selection:
    concept: Concept
    reason: str  # "review" | "new"


def select_next(subject: str) -> Selection | None:
    """Pick the next concept to study for `subject`, with the reason it was chosen.

    A concept is available once all its prerequisites have been seen at least once.
    Overdue review cards (ranked by recall urgency × exam weight) take priority;
    otherwise the highest-weighted unseen concept opens the frontier.
    """
    concepts = dao.get_concepts(subject)
    states = {c.id: store.get_or_create(c.id) for c in concepts}
    introduced = {cid: cs.reps >= 1 for cid, cs in states.items()}
    available = [
        c for c in concepts if all(introduced.get(p, False) for p in c.prerequisites)
    ]
    if not available:
        return None

    now = datetime.now(UTC)
    overdue: list[tuple[float, Concept]] = []
    frontier: list[tuple[int, Concept]] = []

    for concept in available:
        cs = states[concept.id]
        if cs.reps == 0:
            frontier.append((concept.exam_weight, concept))
        elif cs.due is not None and cs.due <= now:
            overdue.append((_urgency(cs, now) * concept.exam_weight, concept))

    if overdue:
        return Selection(max(overdue, key=lambda x: x[0])[1], "review")
    if frontier:
        return Selection(max(frontier, key=lambda x: x[0])[1], "new")
    return None


def _urgency(cs: CardState, now: datetime) -> float:
    """1 - retrievability, so the most-forgotten overdue card ranks highest."""
    if cs.stability is None or cs.stability <= 0 or cs.due is None:
        return 1.0
    elapsed = (now - cs.due).total_seconds() / 86400
    return max(0.0, 1.0 - retrievability(elapsed + cs.stability, cs.stability))
