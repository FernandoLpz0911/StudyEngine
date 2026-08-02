"""Whether the gate is open, and what it would take to open it.

The quota is denominated in *correct* answers against the `daily_goal` number —
one configured number, two readings (ADR-0005). Nothing here touches a display,
so the whole decision is testable headlessly and the window layer stays dumb.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from engine import config, settings
from engine.db import dao
from engine.gate import schedule


@dataclass(frozen=True)
class GateStatus:
    """A complete answer to 'is the gate open, and why' — safe to serialise."""

    is_open: bool
    reason: str  # paid | bailed | retired | exam_eve | closed
    subject: str
    quota: int
    correct: int
    remaining: int
    bails_left: int
    bails_ration: int
    exam_date: str | None
    days_left: int | None
    concepts_total: int
    concepts_seen: int
    coverage_on_track: bool
    projected_score: float
    questions_total: int
    pass_mark: int
    ready_target: int
    projection_passing: bool

    def as_dict(self) -> dict:
        return asdict(self)


def local_now() -> datetime:
    """Wall-clock time in the learner's study day, matching the streak boundary.

    Naive on purpose: `schedule` compares it against exam dates built from naive
    datetimes, and both sides are already in the learner's zone.
    """
    return dao.local_now().replace(tzinfo=None)


def bails_left() -> int:
    """How many bails remain in the trailing window.

    The window is a rolling duration, not a calendar span, so it is measured in
    real elapsed time against the stored UTC timestamps — no local-day conversion,
    which would otherwise skew the cutoff by the zone's offset.
    """
    spent = dao.count_bails_since(config.GATE_BAIL_WINDOW_DAYS)
    return max(0, config.GATE_BAIL_RATION - spent)


def status(now: datetime | None = None) -> GateStatus:
    """Everything the gate and its UI need to decide what to show."""
    now = now or local_now()
    # `now` stays wall-clock — the exam-eve rule is about the hour on the clock —
    # but everything counted per day uses the study day, which turns over at
    # DAY_ROLLOVER_HOUR. Reading the calendar date here instead would let the gate
    # demand a fresh quota at midnight from someone still mid-session.
    today = dao.study_today(now)
    subject = config.GATE_SUBJECT
    exam = dao.get_exam_date(subject)
    quota = settings.get_int("daily_goal")
    correct = dao.count_correct_today(subject=subject, today=today)
    left = bails_left()
    days_left = None if exam is None else schedule.days_until(exam, today)

    suspended = schedule.suspension_reason(exam, now, config.GATE_EVE_HOUR)
    if suspended is not None:
        reason = suspended
        is_open = True
    elif dao.bailed_today(today):
        reason, is_open = "bailed", True
    elif correct >= quota:
        reason, is_open = "paid", True
    else:
        reason, is_open = "closed", False

    # The gate is the one surface with guaranteed daily attention, so it carries
    # the pace readout: being behind on coverage should be impossible to not see.
    from engine.analytics import pace as pace_module
    from engine.analytics.projection import projected_score
    pace = pace_module.subject_pace(subject, today=today)
    projection = projected_score(subject)

    return GateStatus(
        is_open=is_open,
        reason=reason,
        subject=subject,
        quota=quota,
        correct=correct,
        remaining=max(0, quota - correct),
        bails_left=left,
        bails_ration=config.GATE_BAIL_RATION,
        exam_date=None if exam is None else exam.isoformat(),
        days_left=days_left,
        concepts_total=pace.total,
        concepts_seen=pace.seen,
        coverage_on_track=pace.coverage_on_track,
        projected_score=projection.score,
        questions_total=projection.questions,
        pass_mark=projection.pass_mark,
        ready_target=projection.target,
        projection_passing=projection.passing,
    )


def should_raise(now: datetime | None = None) -> bool:
    """Whether the gate is allowed to come up right now.

    Separate from `status()` on purpose. `status()` answers "is the quota paid",
    which the running gate polls to decide when to let go; this answers "should a
    gate appear at all", which additionally refuses if one already appeared today.
    Folding the two together would make a gate release itself the instant it
    recorded its own raise.

    One raise per local day, whatever became of it — paid, bailed, or killed. That
    caps the interruption at a single predictable event instead of a nag every
    watchdog tick, at the cost of making a killed gate a free day (ADR-0006).
    """
    now = now or local_now()
    if status(now).is_open:
        return False
    return not dao.raised_today(dao.study_today(now))


def spend_bail(now: datetime | None = None) -> GateStatus:
    """Open the gate for the rest of the day at the cost of one rationed bail.

    Refuses when the ration is exhausted; the learner still has the TTY, which is
    inconvenient by design rather than impossible (ADR-0004).
    """
    now = now or local_now()
    if bails_left() <= 0:
        raise ValueError("no bails left in the current window")
    dao.record_bail(today=dao.study_today(now))
    return status(now)
