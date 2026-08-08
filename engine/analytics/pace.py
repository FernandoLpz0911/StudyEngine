"""Whether a subject is on course for its exam, and what today owes toward it.

Readiness has two parts that fail in different ways. Mastery degrades gracefully —
a concept at 0.6 on exam day is worth something. Coverage does not: a concept
never introduced is worth nothing, and it cannot be fixed late, because a first
exposure in the final week can only be crammed. So coverage gets a deadline of its
own, `CONSOLIDATION_DAYS` before the exam, and today's share of the remaining
introductions is derived from it (ADR-0007).

The arithmetic is pure functions of counts and dates; only `subject_pace` reads
the database, so the pacing rules are testable without one.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from math import ceil

from engine.config import CONSOLIDATION_DAYS


def coverage_deadline(
    exam: date | None, consolidation_days: int = CONSOLIDATION_DAYS
) -> date | None:
    """The day by which every concept must have been seen at least once.

    Derived from the exam date rather than configured separately: a second date
    would be one more thing to keep in sync, and it would silently contradict the
    exam date the moment a sitting moved.
    """
    if exam is None:
        return None
    return exam - timedelta(days=consolidation_days)


def intro_quota(unseen: int, days_to_deadline: int | None, cap: int) -> int:
    """How many brand-new concepts today owes, bounded by the new-per-day cap.

    Self-correcting by construction: the divisor shrinks each day, so a skipped
    day raises tomorrow's share without anyone tracking a debt. Zero once coverage
    is complete, which retires the whole mechanism for the rest of the exam run.

    With no exam date there is no deadline and so no owed introductions — the
    ordinary reviews-first frontier still opens whenever nothing is due.
    """
    if unseen <= 0 or days_to_deadline is None:
        return 0
    if days_to_deadline <= 0:
        return min(unseen, cap)  # deadline blown: introduce as fast as the cap allows
    return min(ceil(unseen / days_to_deadline), cap)


def intro_owed(subject: str, today: date | None = None) -> int:
    """Introductions this subject still owes *today*, after what it already did.

    Deliberately cheap — three queries, no mastery — because selection calls it
    for every item served. `subject_pace` is the richer read for display.
    """
    from engine import settings
    from engine.db import dao

    today = today or dao.study_today()
    deadline = coverage_deadline(dao.get_exam_date(subject))
    if deadline is None:
        return 0
    done = dao.count_new_concepts_today(today=today, subject=subject)
    # The quota is a share of the backlog as it stood at the *start* of the day.
    # Recomputing it from the shrinking count would let the target fall to meet
    # the work already done — ceil(28/13) is 3, but after two introductions
    # ceil(26/13) is 2, which is what has been done, so the third never happens
    # and coverage quietly runs a day late for every day with a remainder.
    backlog = dao.count_unseen_concepts(subject) + done
    owed = intro_quota(backlog, (deadline - today).days, settings.get_int("new_per_day"))
    return max(0, owed - done)


@dataclass(frozen=True)
class Pace:
    """A subject's standing against its exam date — safe to serialise."""

    subject: str
    total: int
    seen: int
    mastered: int
    unseen: int
    exam_date: str | None
    coverage_deadline: str | None
    days_to_exam: int | None
    days_to_coverage: int | None
    intro_owed_today: int
    intro_done_today: int
    coverage_on_track: bool

    def as_dict(self) -> dict:
        return asdict(self)


def subject_pace(subject: str, today: date | None = None) -> Pace:
    """Read the subject's current standing: coverage, mastery, and what today owes."""
    from engine import settings
    from engine.analytics.readiness import concept_mastery, mastery_bar
    from engine.db import dao
    from engine.scheduler import store

    today = today or dao.study_today()
    concepts = dao.get_concepts(subject)
    states = {c.id: store.get_or_create(c.id) for c in concepts}
    seen = sum(1 for c in concepts if states[c.id].reps > 0)
    mastered = sum(
        1 for c in concepts if concept_mastery(c.id) >= mastery_bar(c.id, subject)
    )
    unseen = len(concepts) - seen

    exam = dao.get_exam_date(subject)
    deadline = coverage_deadline(exam)
    days_to_exam = None if exam is None else (exam - today).days
    days_to_coverage = None if deadline is None else (deadline - today).days

    cap = settings.get_int("new_per_day")
    owed = intro_quota(unseen, days_to_coverage, cap)
    done = dao.count_new_concepts_today(subject=subject, today=today)
    # Behind means the cap is now the binding constraint: even spending the full
    # daily allowance of introductions no longer clears the backlog in time.
    on_track = unseen == 0 or (
        days_to_coverage is not None
        and days_to_coverage > 0
        and unseen <= cap * days_to_coverage
    )

    return Pace(
        subject=subject,
        total=len(concepts),
        seen=seen,
        mastered=mastered,
        unseen=unseen,
        exam_date=None if exam is None else exam.isoformat(),
        coverage_deadline=None if deadline is None else deadline.isoformat(),
        days_to_exam=days_to_exam,
        days_to_coverage=days_to_coverage,
        intro_owed_today=owed,
        intro_done_today=done,
        coverage_on_track=on_track,
    )
