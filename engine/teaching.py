"""Which teaching stage a concept is owed: study it, pair it, or solve it alone.

A test-only loop teaches nothing to a learner who cannot yet retrieve. Eighteen
attempts at one concept left its FSRS stability at 0.0 — every answer a coin
flip, every interval crashed back under a day, no retention accumulating. What
was missing is an instructional step: something that happens between "missed it"
and "here it is again tomorrow".

So an item is served at one of three stages, and the stage is *derived* from the
log rather than stored, for the same reason resting is (see `availability`): a
stored flag has to be maintained, and it goes stale the moment the evidence moves.

  study   the worked solution is shown *first*, then the same problem is answered
          from it. A study trial is not evidence about the learner and never
          reaches FSRS or accuracy — it is the teaching, not the test.
  paired  a fully worked example of a different instance is shown, then a fresh
          problem is solved unaided. Scaffolded, so it advances the schedule but
          is excluded from measured accuracy.
  solo    the bare problem. The only stage that measures anything.

Keeping `solo` the sole contributor to accuracy is what stops the ladder from
inflating readiness: a projected score built from scaffolded answers would
measure how well the learner can copy a solution.

Pure functions over primitives — no database, no engine imports beyond config —
so every promotion and demotion rule is unit-testable.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from engine.config import (
    ACCURACY_FLOOR,
    MAX_CONSECUTIVE_STUDY,
    PREREQ_ACCURACY_BONUS,
    PREREQ_REACH_SATURATION,
    STUCK_MIN_REPS,
    STUCK_MISSES,
    STUCK_STABILITY_DAYS,
)

STUDY = "study"
PAIRED = "paired"
SOLO = "solo"

#: Stages whose answers are the learner's own work, and so may be measured.
MEASURED_STAGES = (SOLO,)
#: Stages that advance the FSRS schedule (a study trial is teaching, not evidence).
SCHEDULED_STAGES = (SOLO, PAIRED)


@dataclass(frozen=True)
class Attempt:
    """One graded attempt on a concept, for deriving its stage. Most recent first."""

    stage: str
    correct: bool
    #: The learner declined to guess. A miss either way, but unambiguous about
    #: *why* — a wrong answer could be a slip, this could not be.
    dont_know: bool = False


def required_accuracy(
    reach: int,
    floor: float = ACCURACY_FLOOR,
    bonus: float = PREREQ_ACCURACY_BONUS,
    saturation: int = PREREQ_REACH_SATURATION,
) -> float:
    """The bar this concept must clear, raised by how much is built on top of it.

    A foundation carries every concept above it: shaky conditional probability
    does not cost its own marks, it costs Bayes, conditional expectation, and the
    double-expectation identity as well. So the standard scales with downstream
    reach — the same number the frontier is already ordered by — rather than
    being one flat threshold for a leaf and a gateway alike.

    Saturating rather than linear: past a handful of dependents the concept is
    already "foundational", and an unbounded ramp would demand accuracy no honest
    measurement reaches.
    """
    if saturation <= 0:
        return min(0.99, floor + bonus)
    return min(0.99, floor + bonus * min(1.0, reach / saturation))


def _accuracy(attempts: Sequence[Attempt], stages: Sequence[str]) -> float | None:
    """Fraction correct over the attempts made at `stages`; None if there are none."""
    scoped = [a for a in attempts if a.stage in stages]
    if not scoped:
        return None
    return sum(1 for a in scoped if a.correct) / len(scoped)


def solo_accuracy(attempts: Sequence[Attempt]) -> float | None:
    """Measured accuracy — unscaffolded attempts only."""
    return _accuracy(attempts, MEASURED_STAGES)


def _trailing_misses(attempts: Sequence[Attempt]) -> int:
    """Consecutive misses at the head of the history, ignoring study trials.

    Study trials are excluded because failing one means the solution was misread,
    not that the concept was forgotten — and counting them would let the
    remediation keep re-triggering itself.
    """
    misses = 0
    for attempt in attempts:
        if attempt.stage == STUDY:
            continue
        if attempt.correct:
            break
        misses += 1
    return misses


def is_stuck(
    reps: int,
    stability: float | None,
    attempts: Sequence[Attempt],
    required: float,
    misses: int = STUCK_MISSES,
    min_reps: int = STUCK_MIN_REPS,
    stability_floor: float = STUCK_STABILITY_DAYS,
) -> bool:
    """Whether testing this concept again would just be another coin flip.

    Three signals, because they catch different failures:

    - a *don't-know* is immediate: the learner has said plainly that nothing is
      there to retrieve, which is better evidence than any inference the log
      could make, and waiting for two more of them wastes two items proving
      something already stated;
    - a run of consecutive wrong answers is an acute break — the concept is not
      available right now and a fourth attempt will not make it available;
    - many reps whose stability never leaves the floor is the chronic case, the
      treadmill this module exists for. Reps alone are not enough: a concept can
      legitimately need many reviews. It is reps *plus* a schedule that has
      learned nothing *plus* accuracy under its own bar.
    """
    if attempts and attempts[0].dont_know:
        return True
    if _trailing_misses(attempts) >= misses:
        return True
    if reps < min_reps:
        return False
    if stability is not None and stability >= stability_floor:
        return False
    accuracy = solo_accuracy(attempts)
    return accuracy is not None and accuracy < required


def graduated_from_paired(paired_accuracy: float | None, required: float) -> bool:
    """Whether the scaffold has been earned away.

    Promotion out of `paired` cannot wait on solo accuracy, because a concept
    held at `paired` never produces a solo attempt — the bar it must clear would
    be measured from evidence the stage itself prevents. So it is judged at the
    rung it is standing on, against that concept's own `required` accuracy.

    That makes promotion and demotion the *same* comparison rather than a streak
    rule going up and an accuracy rule coming down (ADR-0014). A fixed streak
    ignored the bar entirely, so a gateway concept graduated on exactly the same
    evidence as a leaf — two correct guided answers once released a concept whose
    unaided accuracy was 0.64 against a requirement of 0.92.

    A `paired` item is easier than a `solo` one, so clearing 0.92 here is a
    weaker test than clearing it unaided. That is accepted deliberately: a second,
    higher scaffolded threshold would be one more number to justify, and the
    concept still has to hold its bar unaided afterwards or it falls straight back.
    """
    return paired_accuracy is not None and paired_accuracy >= required


def _study_exhausted(attempts: Sequence[Attempt], cap: int = MAX_CONSECUTIVE_STUDY) -> bool:
    """Whether consecutive study trials have hit their cap.

    A failed study trial normally repeats — re-reading a solution you could not
    reproduce is exactly the right response. But an unbounded repeat is a dead
    end that never returns the concept to testing, so after `cap` in a row the
    ladder moves on regardless and lets the scaffolded attempt find the gap.
    """
    head = attempts[:cap]
    return len(head) == cap and all(a.stage == STUDY for a in head)


def stage_for(
    reps: int,
    stability: float | None,
    attempts: Sequence[Attempt],
    required: float,
    solo_acc: float | None = None,
    paired_acc: float | None = None,
) -> str:
    """The stage this concept is owed next. `attempts` is most-recent-first.

    `solo_acc` and `paired_acc` are the guessing-corrected rates at those rungs,
    passed in rather than counted from `attempts` so that the correction is
    applied once, in the DAO, over a window wider than the stage history.

    Order matters: the study-trial follow-up is resolved before the stuck check,
    or a concept that entered remediation on a run of misses would be pinned in
    `study` by that same run for as long as the window remembers it.
    """
    if reps == 0 and not attempts:
        return STUDY  # a first contact is a worked example, not a test you fail

    if attempts and attempts[0].stage == STUDY:
        if attempts[0].correct or _study_exhausted(attempts):
            return PAIRED
        return STUDY

    if is_stuck(reps, stability, attempts, required):
        return STUDY

    if solo_acc is None:
        solo_acc = solo_accuracy(attempts)
    if solo_acc is not None and solo_acc >= required:
        return SOLO
    if graduated_from_paired(paired_acc, required):
        return SOLO
    return PAIRED
