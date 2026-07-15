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
