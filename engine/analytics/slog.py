"""Slogs: concepts that cost disproportionate *time*.

A leech costs disproportionate *attempts* — it is forgotten over and over. A slog
is the other pathology, and nothing in the system reported it before: a concept
answered *correctly* but always slowly. On a timed paper that fails in its own
way, and it is invisible to accuracy, to FSRS, and to the projected score, all of
which are indifferent to how long a right answer took.

Two readings, because the fixes differ:

  time-to-understand   slow at the scaffolded rungs — the worked example is not
                       landing, the theory is unclear, or the statement is
                       confusing. An authoring problem.
  time-to-solve        slow unaided — the method is known but not fluent. A
                       practice problem.

Measured relative to the subject's own median for the same reading, never against
an absolute threshold: a number that works for an ODE does not work for a
flashcard, and any constant would need retuning whenever content changed. The
relative form self-calibrates.

**Diagnostic only.** This feeds no schedule, no accuracy, no mastery, no
projection and no selection (ADR-0014). It exists to tell the *author* where to
fix a generator, rewrite a `theory_md`, or split a concept that is doing too much.
The moment it feeds the study loop it becomes one more thing that can drift out of
true, and the loop already has enough of those.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median

from engine.config import SLOG_MIN_SAMPLES, SLOG_MULTIPLE


@dataclass(frozen=True)
class Slog:
    """One concept's time cost against its subject's norm."""

    concept_id: str
    name: str
    #: Median seconds at the scaffolded rungs; None below the sample floor.
    understand_s: float | None
    #: Median seconds unaided; None below the sample floor.
    solve_s: float | None
    slow_to_understand: bool
    slow_to_solve: bool

    def as_dict(self) -> dict:
        return asdict(self)


def _median_or_none(values: list[float], min_samples: int) -> float | None:
    """Median once there is enough of it to mean anything.

    A median of one attempt is that attempt, and flagging a concept as a slog on
    a single slow answer would mostly report interruptions.
    """
    return median(values) if len(values) >= min_samples else None


def flagged(
    value: float | None, norm: float | None, multiple: float = SLOG_MULTIPLE
) -> bool:
    """Whether a timing sits far enough above its subject's norm to be worth
    looking at. No norm means no comparison, which is not the same as no problem —
    it is silence, and silence is the honest answer with nothing to compare to."""
    return value is not None and norm is not None and norm > 0 and value >= norm * multiple


def subject_slogs(
    subject: str,
    multiple: float = SLOG_MULTIPLE,
    min_samples: int = SLOG_MIN_SAMPLES,
) -> list[Slog]:
    """Every concept's time cost, slowest first, with the two flags set.

    Returns all concepts with timing evidence rather than only the flagged ones:
    the ranking is the useful part, and a report that shows only failures gives no
    sense of what normal looks like.
    """
    from engine.db import dao

    times = dao.stage_times(subject)
    names = {c.id: c.name for c in dao.get_concepts(subject)}

    understand = {
        cid: m
        for cid, buckets in times.items()
        if (m := _median_or_none(buckets["understand"], min_samples)) is not None
    }
    solve = {
        cid: m
        for cid, buckets in times.items()
        if (m := _median_or_none(buckets["solve"], min_samples)) is not None
    }
    understand_norm = median(understand.values()) if understand else None
    solve_norm = median(solve.values()) if solve else None

    rows = [
        Slog(
            concept_id=cid,
            name=names.get(cid, cid),
            understand_s=None if (u := understand.get(cid)) is None else round(u),
            solve_s=None if (s := solve.get(cid)) is None else round(s),
            slow_to_understand=flagged(understand.get(cid), understand_norm, multiple),
            slow_to_solve=flagged(solve.get(cid), solve_norm, multiple),
        )
        for cid in times
    ]
    rows.sort(key=lambda r: max(r.solve_s or 0, r.understand_s or 0), reverse=True)
    return rows
