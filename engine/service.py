"""Shared study-item service: build a servable item and grade an answer.

Used by both the CLI and the HTTP API so problem generation, recall presentation,
and objective grading have one implementation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

from engine import teaching
from engine.db import dao
from engine.db.dao import Concept
from engine.feedback.solve import worked_solution
from engine.generation.base import generate, pick_ask, random_seed
from engine.grading import derive_grade, grade_answer
from engine.recall.cards import as_question

LETTERS = ["a", "b", "c", "d"]
GRADE_LABEL = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}


@dataclass
class StudyItem:
    concept_id: str
    concept_name: str
    subject: str
    reason: str
    kind: str
    question: str
    choices: list[str]
    correct: str
    explain: list[str]
    seed: int
    params: dict
    theory: str | None = None
    explanations: dict = field(default_factory=dict)
    tolerance: float = 1e-3
    stage: str = teaching.SOLO
    #: The worked example shown *before* the learner answers. Populated at the
    #: `study` stage (this problem's own solution) and at `paired` (a solved
    #: sibling problem). Empty at `solo`, where the item is bare by definition.
    example: list[str] = field(default_factory=list)
    example_statement: str = ""
    #: Options offered; 0 for free response. Logged so the guessing correction
    #: knows how much of a correct answer could have been luck.
    choices_n: int = 0


def stage_for_concept(concept: Concept, reach: int | None = None) -> str:
    """The teaching stage this concept is owed next (ADR-0013).

    Derived from the log every time it is served rather than stored, so it tracks
    the evidence instead of having to be kept in step with it.
    """
    from engine.config import (
        MASTERY_ACCURACY_WINDOW,
        PAIRED_PROMOTE_WINDOW,
        TEACHING_WINDOW,
    )
    from engine.scheduler import store

    if reach is None:
        reach = concept_reach(concept.subject).get(concept.id, 0)
    state = store.get_or_create(concept.id)
    attempts = [
        teaching.Attempt(stage, correct, dont_know)
        for stage, correct, dont_know in dao.recent_attempts(
            concept.id, TEACHING_WINDOW
        )
    ]
    return teaching.stage_for(
        state.reps,
        state.stability,
        attempts,
        teaching.required_accuracy(reach),
        solo_acc=dao.get_concept_accuracy(concept.id, MASTERY_ACCURACY_WINDOW),
        paired_acc=dao.stage_accuracy(
            concept.id, teaching.PAIRED, PAIRED_PROMOTE_WINDOW
        ),
    )


def concept_reach(subject: str) -> dict[str, int]:
    """How many concepts each one transitively unlocks, for the raised bar.

    Cached per subject for the process: the prerequisite graph is seed data and
    does not change while the engine runs, and the walk is called for every item
    served.
    """
    cached = _REACH_CACHE.get(subject)
    if cached is None:
        from engine.scheduler.policy import downstream_reach
        cached = downstream_reach(dao.get_concepts(subject))
        _REACH_CACHE[subject] = cached
    return cached


_REACH_CACHE: dict[str, dict[str, int]] = {}


def build_item(
    concept: Concept, rng: np.random.Generator, reason: str = "", stage: str | None = None
) -> StudyItem:
    """Produce a servable item from a concept (generator problem or recall card).

    The stage decides how much of the answer is shown before it is asked for: at
    `study` the item carries its own worked solution, at `paired` a solved sibling
    problem, at `solo` nothing (ADR-0013).
    """
    stage = stage or stage_for_concept(concept)
    if concept.mode == "generator" and concept.generator:
        spec = concept.generator
        ask = pick_ask(spec["params"]["ask"])
        seed = random_seed()
        problem = generate(spec["kind"], ask, spec["params"], seed)
        # Always free response (ADR-0014). Options let a learner reason backwards
        # to an answer they could not produce, and a lucky quarter of them lands —
        # a false positive in the one number every readiness signal is built from.
        # The ladder, not a list of choices, is what supports a concept that is
        # not yet answerable.
        choices: list[str] = []
        # Prefer the generator's own worked solution (shares the closed form);
        # fall back to the legacy solver registry for unmigrated subjects.
        explain = problem.explain or worked_solution(spec["kind"], ask, problem.params)
        example, example_statement = _example_for(spec, ask, stage, explain, problem)
        return StudyItem(
            concept.id, concept.name, concept.subject, reason,
            f"{spec['kind']}:{ask}", problem.statement, choices,
            f"{problem.correct_answer:.3f}",
            explain, seed, problem.params,
            theory=concept.theory_md, tolerance=problem.tolerance,
            stage=stage, example=example, example_statement=example_statement,
        )
    question = as_question(concept, rng)
    # A recall card has no derivation to work through, so its study trial is the
    # answer shown up front and then produced — the card read, not guessed at.
    #
    # There is no middle rung available to it: with no worked example to pair
    # against, a `paired` recall card would be *identical* to a `solo` one while
    # being excluded from measurement, which discards real evidence for nothing.
    # So the ladder has two rungs here, not three.
    if stage == teaching.PAIRED:
        stage = teaching.SOLO
    example = [f"Answer: {question.correct}"] if stage == teaching.STUDY else []
    return StudyItem(
        concept.id, concept.name, concept.subject, reason, "recall",
        question.question, question.choices, question.correct,
        [f"Correct answer: {question.correct}"], 0, {},
        theory=concept.theory_md, explanations=concept.card_explanations,
        stage=stage, example=example, choices_n=len(question.choices),
    )


def _example_for(
    spec: dict, ask: str, stage: str, explain: list[str], problem
) -> tuple[list[str], str]:
    """The worked example to show before the question, if the stage wants one.

    At `study` it is this problem's own solution: the learner reads the derivation
    and then reproduces the answer from it, which is the teaching trial.

    At `paired` it is a *different* instance of the same generator, solved in
    full. A sibling rather than the same numbers, because an example whose answer
    is also the answer being asked for teaches copying; one that shares only the
    method teaches the method.
    """
    if stage == teaching.STUDY:
        return list(explain), ""
    if stage != teaching.PAIRED:
        return [], ""
    sibling = generate(spec["kind"], ask, spec["params"], random_seed())
    worked = sibling.explain or worked_solution(spec["kind"], ask, sibling.params)
    if not worked:
        return [], ""
    return (
        [*worked, f"Answer: {sibling.correct_answer:.3f}"],
        sibling.statement,
    )


def next_retry(
    retry_queue: list[tuple[str, int]], index: int, force: bool
) -> Concept | None:
    """Pop the next queued missed concept whose spacing gap has elapsed.

    Suppressed concepts are skipped (left queued): the retry path bypasses policy,
    so it must honor bury/suspend itself or a just-hidden concept comes right back.
    Shared by the API and CLI so the skip logic lives in one place.
    """
    if not retry_queue:
        return None
    suppressed = dao.suppressed_concept_ids()
    for i, (cid, ready) in enumerate(retry_queue):
        if cid in suppressed:
            continue
        if force or index >= ready:
            concept = dao.get_concept(cid)
            retry_queue.pop(i)
            if concept is not None:
                return concept
    return None


def explanation_for(answer: str, item: StudyItem) -> str:
    """Why the learner's wrong choice is wrong, if the author supplied one."""
    if not item.explanations:
        return ""
    answer = answer.strip()
    if answer.lower() in LETTERS and LETTERS.index(answer.lower()) < len(item.choices):
        answer = item.choices[LETTERS.index(answer.lower())]
    return item.explanations.get(answer, "")


def log_item_shown(session_id: int, item: StudyItem) -> int:
    """Persist that an item was served; return the interaction id."""
    return dao.log_shown(
        session_id, item.concept_id, item.subject, item.kind,
        seed=item.seed, params_json=json.dumps(item.params), correct_answer=item.correct,
        reason=item.reason, stage=item.stage, choices_n=item.choices_n,
    )


#: What the learner sends instead of an answer to decline guessing. A sentinel
#: rather than an empty string, because a blank submission and a deliberate
#: "I don't know" mean different things and only one of them is evidence.
DONT_KNOW = "__dont_know__"


def is_dont_know(answer: str) -> bool:
    return answer.strip() == DONT_KNOW


def is_correct(answer: str, item: StudyItem) -> bool:
    """Grade a chosen answer — a letter, the option text, or a typed numeric value."""
    answer = answer.strip()
    if is_dont_know(answer):
        return False
    if answer.lower() in LETTERS and LETTERS.index(answer.lower()) < len(item.choices):
        return item.choices[LETTERS.index(answer.lower())] == item.correct
    tolerance = item.tolerance
    if not item.choices:
        # Typed free response: the key is rounded to 3 decimals, and the learner may
        # round differently, so widen to a relative tolerance around the true value.
        from engine.config import TYPED_REL_TOLERANCE
        try:
            tolerance = max(tolerance, abs(float(item.correct)) * TYPED_REL_TOLERANCE)
        except ValueError:
            pass
    return grade_answer(answer, item.correct, tolerance)


@dataclass
class SettleResult:
    """The log-wide result of settling one answer — the canonical Settle (see
    CONTEXT.md). No session-local state: `StudyLoop.settle` folds streak, combo,
    reward, and XP on top of this."""
    correct: bool
    grade: int
    records: list[str]
    next_review_days: int | None
    why_wrong: str
    ask_mnemonic: bool
    ask_reflection: bool
    #: The explanation was opened before answering. Echoed back rather than
    #: recomputed so the front ends render the same fact the log recorded.
    aided: bool = False


@dataclass
class AnswerOutcome:
    """Everything an answer produces for rendering, assembled by `StudyLoop.settle`
    from a `SettleResult` plus the session-local framing. The front ends only
    render these (JSON vs stdout)."""
    correct: bool
    grade: int
    records: list[str]
    reward: str
    combo: str
    combo_break: str
    streak: int
    best_streak: int
    xp: int
    next_review_days: int | None
    why_wrong: str
    ask_mnemonic: bool
    ask_reflection: bool
    stage: str
    #: The explanation was opened before answering, so this answer bought no
    #: readiness — it is credited to ascent and to the quota, and nothing else.
    aided: bool


def settle_answer(
    item_id: int,
    item: StudyItem,
    raw_answer: str,
    elapsed_ms: int,
    tracker,
    aided: bool = False,
) -> SettleResult:
    """Settle one answer's log-wide effects: the write path shared by both front
    ends via `StudyLoop`.

    Logs the answer, advances FSRS state, banks quests, records the retry debt,
    and detects personal-best crossings. Session-local framing (streak, combo,
    reward, XP) is *not* here — that is per-session state the StudyLoop owns.
    """
    from engine.config import LEECH_LAPSES, MAX_ANSWER_MS
    from engine.quests import settle

    # Clamped once, before it can reach the grade, the log, or the fastest-answer
    # record. The client reports active time, but an old tab left open still posts
    # wall clock, and a single 43-hour "answer" both grades Hard and permanently
    # skews any timing statistic derived from the log.
    elapsed_ms = max(0, min(elapsed_ms, MAX_ANSWER_MS))
    declined = is_dont_know(raw_answer)
    correct, grd = grade(raw_answer, elapsed_ms, item, aided=aided)
    # Read before this answer lands in the log, or it can never beat the record.
    answered_today_before = dao.count_answered_today()
    dao.log_answered(
        item_id, None if declined else (raw_answer or None),
        correct, grd, elapsed_ms, dont_know=declined, aided=aided,
    )

    tracker.refresh()  # re-snapshot baselines if the local day rolled over
    # Records are earned unaided or not at all. A study trial has the answer on
    # screen, so it can be "answered correctly" in two seconds — which would take
    # the fastest-answer record permanently and pad the record run with work that
    # demonstrated nothing. The same reasoning that keeps scaffolding out of
    # accuracy keeps it out of the trophy cabinet.
    records = (
        tracker.detect(correct, elapsed_ms, answered_today_before)
        if item.stage == teaching.SOLO and not aided
        else []
    )

    new_state = _apply_schedule(item, correct, grd)
    # Bank any quest this answer completed — after store.save, so a clean-queue
    # quest can bank on the very answer that clears the last due review.
    settle()

    if correct:
        dao.remove_pending_retry(item.concept_id)  # debt paid, if any
    else:
        dao.add_pending_retry(item.concept_id)  # owed a re-test even across sessions

    is_leech = dao.get_lapses(item.concept_id) >= LEECH_LAPSES
    no_mnemonic = dao.get_mnemonic(item.concept_id) is None
    return SettleResult(
        correct=correct,
        grade=grd,
        records=records,
        next_review_days=_days_until(new_state.due),
        why_wrong="" if correct else explanation_for(raw_answer, item),
        ask_mnemonic=no_mnemonic and (not correct or is_leech),
        # Asked only where it can be answered honestly: a miss on work the learner
        # actually attempted, with numbered steps to point at. After a study trial
        # the solution was already on screen, so "which step lost you" has no
        # meaning, and asking it would train clicking through the prompt.
        ask_reflection=(
            not correct
            and item.stage in teaching.SCHEDULED_STAGES
            and len(item.explain) > 1
        ),
        aided=aided,
    )


def _apply_schedule(item: StudyItem, correct: bool, grade: int):
    """Advance the concept's FSRS state for this answer and persist it.

    A study trial never touches the schedule (ADR-0013). The worked solution was
    on screen, so neither outcome is evidence about recall: crediting a correct
    one would lengthen the interval on a concept that has not been retrieved at
    all, and that is precisely the inflation the ladder exists to avoid.

    A drill is an extra rep on a card that was *not* due, served only to keep the
    day's quota payable, so it updates the schedule asymmetrically (ADR-0008): a
    miss is strong evidence of forgetting and crashes the interval, while getting
    a still-fresh card right says little and leaves the schedule alone. The failed
    drill does not advance `reps`, so failing cannot raise rep-confidence.
    """
    from engine.scheduler import store

    state = store.get_or_create(item.concept_id)
    if item.stage not in teaching.SCHEDULED_STAGES:
        return state
    if item.reason == "drill":
        if correct:
            return state
        state = store.apply_rating(state, 1, subject=item.subject, count_rep=False)
    else:
        state = store.apply_rating(state, grade, subject=item.subject)
    store.save(state)
    return state


def _days_until(due) -> int | None:
    """Whole days until a card's next review (the 'back in N days' open loop)."""
    if due is None:
        return None
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    d = due if due.tzinfo else due.replace(tzinfo=UTC)
    return max(0, (d - now).days)


def grade(
    answer: str, elapsed_ms: int, item: StudyItem, aided: bool = False
) -> tuple[bool, int]:
    """Return (is_correct, derived FSRS grade) for an answer — purely data-based.

    Response time is consulted at the `solo` stage only, and only when the answer
    was unaided (ADR-0014). With an explanation on screen — whether the ladder put
    it there or the learner opened it — the clock cannot distinguish reading from
    solving from copying, so the item grades on correctness alone: a correct one
    Good, a miss Again. The schedule learns from unaided timing or not at all.

    Recall cards and multi-step generator problems have different natural response
    times, so each mode grades speed against its own thresholds.
    """
    from engine.config import (
        GRADE_FAST_MS,
        GRADE_FAST_MS_GEN,
        GRADE_SLOW_MS,
        GRADE_SLOW_MS_GEN,
    )
    correct = is_correct(answer, item)
    if item.stage != teaching.SOLO or aided:
        return correct, 3 if correct else 1
    if item.kind == "recall":
        fast, slow = GRADE_FAST_MS, GRADE_SLOW_MS
    else:
        fast, slow = GRADE_FAST_MS_GEN, GRADE_SLOW_MS_GEN
    return correct, derive_grade(correct, elapsed_ms, fast, slow)
