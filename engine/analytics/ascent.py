"""Ascent: how far a concept has climbed the teaching ladder.

The measure guided work moves, and the answer to "am I needing less help than I
was". Deliberately separate from the [[projected-score]], which only unaided work
moves, because one number cannot honestly say both *"you have worked through this
material"* and *"you would pass on Sunday"* — and a single number asked to do both
ends up saying the more flattering one.

A concept's ascent is its rung plus how far it has come toward leaving that rung:

    (rung_index + progress_within_rung) / 3

where progress within a rung is the same comparison everywhere — measured accuracy
at the rung you are standing on, against that concept's own required accuracy. So
promotion, demotion and this readout are all one rule read three ways.

The property that makes the split safe rather than a second flattering number: on
the top rung the remaining climb *is* unaided accuracy against the bar, so ascent
converges onto readiness exactly as the help stops being needed. The two numbers
meet at the top; the gap between them is precisely how much of the learner's
standing is still propped up.

Nothing here feeds selection, the schedule, drills, resting, or the projection.
It is read, not acted on.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from engine.teaching import PAIRED, SOLO, STUDY

#: Ladder order. The index is the rung already earned; the fraction is the climb
#: out of it, so a concept mid-`paired` scores above one that has just left
#: `study` and below one about to reach `solo`.
RUNGS = (STUDY, PAIRED, SOLO)


def rung_progress(accuracy: float | None, required: float) -> float:
    """How far across the current rung, as measured accuracy against the bar.

    `None` accuracy is no evidence rather than bad evidence, so it reads as no
    progress across the rung — the concept has arrived but not yet shown anything.
    Capped at 1.0: overshooting the bar is what promotes you, not extra credit.
    """
    if accuracy is None or required <= 0:
        return 0.0
    return max(0.0, min(1.0, accuracy / required))


def concept_ascent(stage: str, accuracy: float | None, required: float) -> float:
    """One concept's position on the ladder, in [0, 1].

    A concept at `solo` holding its bar reads 1.0 — fully climbed, no help needed.
    A concept newly dropped to `study` reads near 0 whatever its history, because
    ascent describes where it stands now, not how far it once got. That is the
    honest reading: a concept in remediation *has* lost ground.
    """
    try:
        index = RUNGS.index(stage)
    except ValueError:
        index = 0
    return min(1.0, (index + rung_progress(accuracy, required)) / len(RUNGS))


@dataclass(frozen=True)
class ConceptAscent:
    """One concept's climb, with the parts it was computed from."""

    concept_id: str
    name: str
    stage: str
    ascent: float
    accuracy: float | None
    required: float

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SubjectAscent:
    """A subject's climb: the exam-weighted mean over its concepts."""

    subject: str
    ascent: float
    at_study: int
    at_paired: int
    at_solo: int
    concepts: list[ConceptAscent]

    def as_dict(self) -> dict:
        return {
            "subject": self.subject,
            "ascent": self.ascent,
            "at_study": self.at_study,
            "at_paired": self.at_paired,
            "at_solo": self.at_solo,
            "concepts": [c.as_dict() for c in self.concepts],
        }


def subject_ascent(subject: str) -> SubjectAscent:
    """Every concept's climb plus the exam-weighted aggregate.

    Exam-weighted rather than a flat mean, for the same reason readiness is:
    climbing a concept worth three questions is three times the progress of
    climbing one worth a single question, and a flat mean would let a long tail
    of trivia dominate the headline.

    Unseen concepts count at zero rather than being skipped. They are genuinely
    unclimbed, and dropping them would make the number *rise* as the syllabus
    grew — a progress bar that advances when work is added is worse than none.
    """
    from engine.config import MASTERY_ACCURACY_WINDOW, PAIRED_PROMOTE_WINDOW
    from engine.db import dao
    from engine.service import concept_reach, stage_for_concept
    from engine.teaching import required_accuracy

    concepts = dao.get_concepts(subject)
    reach = concept_reach(subject)
    rows: list[ConceptAscent] = []
    weighted = 0.0
    total_weight = sum(c.exam_weight for c in concepts) or 1

    for concept in concepts:
        stage = stage_for_concept(concept, reach=reach.get(concept.id, 0))
        required = required_accuracy(reach.get(concept.id, 0))
        if stage == SOLO:
            accuracy = dao.get_concept_accuracy(concept.id, MASTERY_ACCURACY_WINDOW)
        elif stage == PAIRED:
            accuracy = dao.stage_accuracy(concept.id, PAIRED, PAIRED_PROMOTE_WINDOW)
        else:
            accuracy = dao.stage_accuracy(concept.id, STUDY, PAIRED_PROMOTE_WINDOW)
        value = concept_ascent(stage, accuracy, required)
        rows.append(
            ConceptAscent(
                concept_id=concept.id,
                name=concept.name,
                stage=stage,
                ascent=round(value, 3),
                accuracy=None if accuracy is None else round(accuracy, 3),
                required=round(required, 3),
            )
        )
        weighted += value * concept.exam_weight

    return SubjectAscent(
        subject=subject,
        ascent=round(weighted / total_weight, 3),
        at_study=sum(1 for r in rows if r.stage == STUDY),
        at_paired=sum(1 for r in rows if r.stage == PAIRED),
        at_solo=sum(1 for r in rows if r.stage == SOLO),
        concepts=rows,
    )
