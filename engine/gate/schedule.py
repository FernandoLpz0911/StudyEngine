"""When the gate is entitled to exist at all — pure functions of the exam date.

The gate serves one sitting. It falls silent on the eve so the learner sleeps and
sits the exam unfought, and retires permanently once that exam is behind them
rather than outliving its own reason (ADR-0004). Everything here is a pure
function of (exam date, now) so the lifecycle is unit-testable without a clock.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta


def days_until(exam: date, today: date) -> int:
    """Whole days from `today` to the exam. Negative once the exam has passed."""
    return (exam - today).days


def is_retired(exam: date | None, today: date) -> bool:
    """True once the sitting is behind us — the gate has done its job and stops.

    Retirement is by date, not by hour: on exam day itself the gate is already
    suppressed by the eve rule, so there is no window where it fires on the way
    to the exam hall.
    """
    return exam is not None and today > exam


def is_eve_suppressed(exam: date | None, now: datetime, eve_hour: int) -> bool:
    """True from `eve_hour` the night before the exam through the end of exam day.

    Sleep the night before is worth more than one more quota, and a gate between
    the learner and the door on exam morning is actively harmful.
    """
    if exam is None:
        return False
    eve = datetime.combine(exam - timedelta(days=1), datetime.min.time()).replace(
        hour=eve_hour
    )
    end_of_exam_day = datetime.combine(exam + timedelta(days=1), datetime.min.time())
    return eve <= now < end_of_exam_day


def suspension_reason(exam: date | None, now: datetime, eve_hour: int) -> str | None:
    """Why the gate must not fire right now, or None if it is free to fire."""
    if is_retired(exam, now.date()):
        return "retired"
    if is_eve_suppressed(exam, now, eve_hour):
        return "exam_eve"
    return None
