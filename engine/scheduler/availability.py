"""Concept availability predicates — the single source for two selection rules.

Two facts about a concept, each expressed once so policy selection, dashboard
readiness, and the due-count HUD can't drift on the subtle suspend/bury semantics
(see CONTEXT.md: Introduced, Due, Suspended, Buried, Suppressed).

Pure functions over primitives — no engine imports — so any caller (including the
low-level DAO) can use them without an import cycle, and they unit-test trivially.
"""
from __future__ import annotations

from datetime import UTC, datetime


def introduced(reps: int, suspended: bool) -> bool:
    """Whether a concept counts as introduced — i.e. unlocks its dependents.

    Seen at least once, or explicitly suspended ("I know this"): a suspended
    prerequisite must not lock everything behind it forever. A one-day bury
    implies no such mastery and is deliberately *not* introduced.
    """
    return reps >= 1 or suspended


def is_rested(
    mastery: float,
    reps: int,
    days_to_exam: int | None,
    rest_mastery: float,
    min_reps: int,
    stop_days: int,
) -> bool:
    """Whether a concept is strong enough to skip reviewing for now.

    A concept held well above the readiness bar is spending the day's quota to
    tell you something already known, while the concepts that decide the exam go
    unpractised. Much of it is also being exercised indirectly: answering a Normal
    question uses variance and standardisation whether or not those are the card
    on screen.

    No stored flag and no second threshold, because resting is self-undoing.
    Mastery carries an FSRS retention factor that decays with time since the last
    review, so a rested concept's score falls on its own and it rejoins the
    rotation without anything having to remember it was resting.

    Resting stops near the sitting: the exam taper exists to leave everything
    fresh on the day, and a concept skipped through the final week would be the
    one thing it missed.
    """
    if days_to_exam is not None and days_to_exam <= stop_days:
        return False
    return reps >= min_reps and mastery >= rest_mastery


def is_due(reps: int, due: datetime | None, now: datetime, suppressed: bool) -> bool:
    """Whether a concept's review is waiting right now.

    Reviewed at least once, its FSRS due time reached, and not currently
    suppressed — a suspended or buried card must not nag. Naive `due` values are
    read as UTC so the comparison never raises on a mixed-awareness timestamp.
    """
    if suppressed or reps <= 0 or due is None:
        return False
    aware = due if due.tzinfo else due.replace(tzinfo=UTC)
    return aware <= now
