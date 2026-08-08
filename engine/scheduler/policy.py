"""Next-concept selection for a subject: overdue reviews first, then new frontier."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from engine.db import dao
from engine.db.dao import Concept
from engine.scheduler import store
from engine.scheduler.availability import introduced, is_due, is_rested
from engine.scheduler.fsrs_core import retrievability
from engine.scheduler.store import CardState


@dataclass
class Selection:
    concept: Concept
    reason: str  # "review" | "new" | "drill"


def downstream_reach(concepts: list[Concept]) -> dict[str, int]:
    """How many concepts each one transitively unlocks.

    Exam weight says how much a concept is worth; reach says how much is stuck
    behind it. Ranking the frontier on weight alone strands the gateways — on
    Exam P every high-weight distribution sits behind a low-weight one — so the
    deep layers open only in the last days of the coverage window, which is
    exactly when there is no time left to space them.
    """
    children: dict[str, list[str]] = {}
    for concept in concepts:
        for prereq in concept.prerequisites:
            children.setdefault(prereq, []).append(concept.id)

    reach: dict[str, int] = {}

    def walk(cid: str, visiting: frozenset[str]) -> set[str]:
        if cid in visiting:  # a malformed cycle must not recurse forever
            return set()
        out: set[str] = set()
        for child in children.get(cid, []):
            out.add(child)
            out |= walk(child, visiting | {cid})
        return out

    for concept in concepts:
        # A cycle would otherwise let a concept reach itself and inflate its rank.
        reach[concept.id] = len(walk(concept.id, frozenset()) - {concept.id})
    return reach


def _frontier_key(concept: Concept, reach: dict[str, int]) -> tuple[int, int]:
    return (reach.get(concept.id, 0), concept.exam_weight)


def _intro_owed(subject: str) -> int:
    """Brand-new concepts the coverage deadline still wants from today (ADR-0007)."""
    from engine.analytics import pace
    return pace.intro_owed(subject)


def _paced(subject: str) -> bool:
    """Whether this subject's introductions are governed by a coverage deadline.

    With an exam date the deadline sets the pace in both directions: it is a floor
    on a busy day and equally a ceiling on a quiet one. Racing ahead would spend
    the new-per-day cap the moment the review queue empties, which is the review
    flood the cap exists to prevent — and it would leave a wall of first exposures
    all maturing at once. Subjects with no exam date keep the old behaviour: the
    frontier opens freely whenever nothing is due.
    """
    from engine.db import dao
    return dao.get_exam_date(subject) is not None


def _rested(concept: Concept, cs: CardState) -> bool:
    """Whether this concept is strong enough to skip reviewing for now.

    Checked only for cards that are otherwise due, so the mastery read costs
    nothing on the far larger set that is not.
    """
    from engine.analytics.readiness import concept_mastery
    from engine.config import MASTERY_TARGET_REPS, REST_MASTERY, REST_STOP_DAYS
    from engine.scheduler.store import _days_to_exam

    return is_rested(
        concept_mastery(concept.id),
        cs.reps,
        _days_to_exam(concept.subject),
        rest_mastery=REST_MASTERY,
        min_reps=MASTERY_TARGET_REPS,
        stop_days=REST_STOP_DAYS,
    )


def _running_ahead(subject: str) -> bool:
    """Whether recent accuracy justifies reaching past the deadline's pace."""
    from engine.config import AHEAD_ACCURACY, AHEAD_WINDOW
    accuracy = dao.recent_accuracy(subject, AHEAD_WINDOW)
    return accuracy is not None and accuracy >= AHEAD_ACCURACY


def _coverage_backstop(subject: str) -> bool:
    """Whether the coverage deadline is now close enough to override the floor.

    The accuracy floor protects consolidation, but coverage is the one part of
    readiness that cannot be repaired late (ADR-0007) — a concept never introduced
    is worth only the guessing floor, and held-back introductions would quietly
    become permanent for a learner whose accuracy never recovers. So the floor
    yields inside `COVERAGE_BACKSTOP_DAYS` of the deadline and the deadline
    resumes driving introductions regardless.
    """
    from engine.analytics.pace import coverage_deadline
    from engine.config import COVERAGE_BACKSTOP_DAYS

    deadline = coverage_deadline(dao.get_exam_date(subject))
    if deadline is None:
        return False
    return (deadline - dao.study_today()).days <= COVERAGE_BACKSTOP_DAYS


def _above_accuracy_floor(subject: str) -> bool:
    """Whether recent unaided accuracy is high enough to take on new material.

    Introducing a concept to a learner answering at 40% widens the surface of the
    same guessing: every new concept becomes several near-term reviews competing
    with the ones already not being retained, and the marks lost to that crowding
    outweigh the marks a first exposure adds. The mirror of `_running_ahead` —
    the same evidence, read as a floor rather than a ceiling.

    Too little evidence reads as "no objection": a subject with a handful of
    answers has not demonstrated a problem, and the frontier is how it gets any.
    """
    from engine.config import ACCURACY_FLOOR, AHEAD_WINDOW
    accuracy = dao.recent_accuracy(subject, AHEAD_WINDOW)
    return accuracy is None or accuracy >= ACCURACY_FLOOR


def _may_introduce(subject: str) -> bool:
    """Whether new concepts may be introduced for this subject at all today."""
    return _above_accuracy_floor(subject) or _coverage_backstop(subject)


def prereq_repair(concept: Concept) -> Concept | None:
    """The prerequisite to re-test *before* re-testing the concept that missed.

    A miss is often not about the concept on screen. Conditional expectation
    fails because conditional probability is shaky, and another attempt at
    conditional expectation practises the failure rather than the cause — which is
    how a concept accumulates eighteen reps without its stability ever leaving the
    floor (ADR-0013).

    Depth one only. Following the chain down would walk the session away from the
    material the exam actually asks about, and the prerequisite's own miss will
    open the next step down on its own if it is really the problem.

    Returns None unless some prerequisite is *weaker* than the concept that just
    missed: if the foundation is the stronger of the two, the miss belongs to the
    concept and re-testing the prereq is a detour.
    """
    from engine.analytics.readiness import concept_mastery

    if not concept.prerequisites:
        return None
    suppressed = dao.suppressed_concept_ids()
    here = concept_mastery(concept.id)
    weakest: tuple[float, Concept] | None = None
    for prereq_id in concept.prerequisites:
        if prereq_id in suppressed:
            continue
        prereq = dao.get_concept(prereq_id)
        if prereq is None or store.get_or_create(prereq_id).reps == 0:
            continue  # never introduced: the frontier's job, not the repair's
        mastery = concept_mastery(prereq_id)
        if mastery < here and (weakest is None or mastery < weakest[0]):
            weakest = (mastery, prereq)
    return None if weakest is None else weakest[1]


def _new_budget_left() -> bool:
    """Whether today's cap on newly introduced concepts still has room.

    Every new concept turns into several near-term reviews, so an uncapped first
    session floods the queue days later. The frontier simply closes for the day
    once the cap is hit; reviews are never limited.
    """
    from engine import settings
    return dao.count_new_concepts_today() < settings.get_int("new_per_day")


def select_next(subject: str) -> Selection | None:
    """Pick the next concept to study for `subject`, with the reason it was chosen.

    A concept is available once all its prerequisites have been seen at least once.

    Introductions the coverage deadline owes today come first, then overdue reviews
    (ranked by recall urgency × exam weight), then the frontier if the daily cap
    still has room. Reviews used to preempt the frontier unconditionally, which
    silently froze coverage: with early reinforcement capping intervals at a day,
    the seen concepts are due again every morning and the frontier is never reached
    (ADR-0007).

    Introductions are additionally held under the accuracy floor (ADR-0013), which
    outranks the deadline's own pace until the coverage backstop takes over.
    """
    concepts = dao.get_concepts(subject)
    states = {c.id: store.get_or_create(c.id) for c in concepts}
    suppressed = dao.suppressed_concept_ids()
    suspended = dao.suspended_concept_ids()
    introduced_map = {
        cid: introduced(cs.reps, cid in suspended) for cid, cs in states.items()
    }
    available = [
        c for c in concepts
        if c.id not in suppressed
        and all(introduced_map.get(p, False) for p in c.prerequisites)
    ]
    if not available:
        return None

    now = datetime.now(UTC)
    overdue: list[tuple[float, Concept]] = []
    frontier: list[Concept] = []

    for concept in available:
        cs = states[concept.id]
        if cs.reps == 0:
            frontier.append(concept)
        elif is_due(cs.reps, cs.due, now, suppressed=False) and not _rested(concept, cs):
            overdue.append((_urgency(cs, now) * concept.exam_weight, concept))

    def best_new() -> Concept:
        reach = downstream_reach(concepts)
        return max(frontier, key=lambda c: _frontier_key(c, reach))

    can_introduce = frontier and _new_budget_left() and _may_introduce(subject)
    if can_introduce and _intro_owed(subject) > 0:
        return Selection(best_new(), "new")
    if overdue:
        return Selection(max(overdue, key=lambda x: x[0])[1], "review")
    # The deadline's pace is a ceiling only while the plan is being kept to. With
    # the day's scheduled work done and accuracy running high, the rest of the
    # syllabus is better met early than waited for.
    if can_introduce and (not _paced(subject) or _running_ahead(subject)):
        return Selection(best_new(), "new")
    return None


def select_drill(subject: str) -> Selection | None:
    """The weakest concept worth an extra, off-schedule rep.

    Supply of quota-payable items is due reviews plus retries, so only *wrong*
    answers regenerate it — answer everything correctly and the day runs dry with
    the quota unpaid and the desktop still locked. Drills top the day back up, and
    aim at the lowest measured mastery, which is also the highest-value thing to be
    practising (ADR-0008).
    """
    from engine.analytics.projection import concept_p_exam

    suppressed = dao.suppressed_concept_ids()
    now = datetime.now(UTC)
    candidates = [
        c for c in dao.get_concepts(subject)
        if c.id not in suppressed and store.get_or_create(c.id).reps > 0
    ]
    if not candidates:
        return None

    def marks_at_stake(concept: Concept) -> float:
        """Marks a perfect concept would add over leaving it where it is.

        Lowest mastery alone ignores what a concept is worth: a weight-3 concept
        at 0.70 carries three times the marks of a weight-1 at 0.50, so practising
        the weaker one is the worse use of a limited day (ADR-0012).
        """
        return concept.exam_weight * (1.0 - concept_p_exam(concept.id, now))

    # Least-drilled-today first, then most marks at stake: everything gets one
    # before anything gets two, so a long top-up spaces rather than masses.
    taken = dao.drills_today(subject)
    best = max(candidates, key=lambda c: (-taken.get(c.id, 0), marks_at_stake(c)))
    return Selection(best, "drill")


def select_global(
    subjects: list[str],
    avoid_subject: str | None = None,
    mode: str = "weak",
    p_correct: dict[str, float] | None = None,
) -> Selection | None:
    """Pick the next item across all subjects — interleaved global spaced repetition.

    mode="weak": prioritise the most-forgotten / lowest-mastery due review, weighted
    by exam weight (or a new concept when nothing is due). mode="confidence": pick
    the due review you are most likely to answer correctly — a warm-up / cool-down
    confidence builder. `avoid_subject` is down-weighted so consecutive items come
    from different subjects.

    When `p_correct` is given (DKT predictions per concept), it replaces the FSRS
    mastery estimate for ranking — so the trained global model drives selection.
    """
    from engine.analytics.readiness import concept_mastery
    from engine.config import INTERLEAVE_PENALTY

    now = datetime.now(UTC)

    def mastery_of(concept: Concept) -> float:
        if p_correct is not None:
            return p_correct.get(concept.id, 0.5)
        return concept_mastery(concept.id, now)
    reviews: list[Concept] = []
    frontier: list[Concept] = []
    all_concepts: list[Concept] = []
    may_introduce: dict[str, bool] = {}
    suppressed = dao.suppressed_concept_ids()
    suspended = dao.suspended_concept_ids()
    for subject in subjects:
        concepts = dao.get_concepts(subject)
        all_concepts.extend(concepts)
        states = {c.id: store.get_or_create(c.id) for c in concepts}
        introduced_map = {
            cid: introduced(cs.reps, cid in suspended) for cid, cs in states.items()
        }
        for concept in concepts:
            if concept.id in suppressed:
                continue
            if not all(introduced_map.get(p, False) for p in concept.prerequisites):
                continue
            cs = states[concept.id]
            if cs.reps == 0:
                # The accuracy floor is per subject, so it is applied per subject
                # here rather than to the merged pool: one subject going badly
                # must not freeze the frontier of the others (ADR-0013).
                if may_introduce.setdefault(subject, _may_introduce(subject)):
                    frontier.append(concept)
            elif is_due(cs.reps, cs.due, now, suppressed=False):
                reviews.append(concept)

    def penalty(concept: Concept) -> float:
        return INTERLEAVE_PENALTY if concept.subject == avoid_subject else 1.0

    def best_new(pool: list[Concept]) -> Concept:
        reach = downstream_reach(all_concepts)
        return max(
            pool, key=lambda c: (reach.get(c.id, 0), c.exam_weight * penalty(c))
        )

    # A subject with an exam date owes introductions on a schedule; those come
    # before reviews, or the coverage deadline is never met (ADR-0007).
    owed = {s for s in subjects if _intro_owed(s) > 0}
    behind = [c for c in frontier if c.subject in owed]
    if behind and _new_budget_left():
        return Selection(best_new(behind), "new")

    if reviews:
        def review_key(concept: Concept) -> float:
            mastery = mastery_of(concept)
            if mode == "confidence":
                return mastery * penalty(concept)
            return (1.0 - mastery) * concept.exam_weight * penalty(concept)

        return Selection(max(reviews, key=review_key), "review")
    unpaced = [c for c in frontier if not _paced(c.subject)]
    if unpaced and _new_budget_left():
        return Selection(best_new(unpaced), "new")
    return None


def _urgency(cs: CardState, now: datetime) -> float:
    """1 - retrievability, so the most-forgotten overdue card ranks highest."""
    if cs.stability is None or cs.stability <= 0 or cs.due is None:
        return 1.0
    elapsed = (now - cs.due).total_seconds() / 86400
    return max(0.0, 1.0 - retrievability(elapsed + cs.stability, cs.stability))
