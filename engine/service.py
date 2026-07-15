"""Shared study-item service: build a servable item and grade an answer.

Used by both the CLI and the HTTP API so problem generation, recall presentation,
and objective grading have one implementation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

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


def _serve_typed(concept: Concept) -> bool:
    """Whether a generator concept has outgrown multiple choice.

    Recognition is easier than recall: once mastery is high the four options give
    the answer away, so the item switches to a typed free response.
    """
    from engine import settings
    from engine.analytics.readiness import concept_mastery
    return concept_mastery(concept.id) >= settings.get_float("typed_answer_mastery")


def build_item(concept: Concept, rng: np.random.Generator, reason: str = "") -> StudyItem:
    """Produce a servable item from a concept (generator problem or recall card)."""
    if concept.mode == "generator" and concept.generator:
        spec = concept.generator
        ask = pick_ask(spec["params"]["ask"])
        seed = random_seed()
        problem = generate(spec["kind"], ask, spec["params"], seed)
        choices = [] if _serve_typed(concept) else (problem.choices or [])
        # Prefer the generator's own worked solution (shares the closed form);
        # fall back to the legacy solver registry for unmigrated subjects.
        explain = problem.explain or worked_solution(spec["kind"], ask, problem.params)
        return StudyItem(
            concept.id, concept.name, concept.subject, reason,
            f"{spec['kind']}:{ask}", problem.statement, choices,
            f"{problem.correct_answer:.3f}",
            explain, seed, problem.params,
            theory=concept.theory_md, tolerance=problem.tolerance,
        )
    question = as_question(concept, rng)
    return StudyItem(
        concept.id, concept.name, concept.subject, reason, "recall",
        question.question, question.choices, question.correct,
        [f"Correct answer: {question.correct}"], 0, {},
        theory=concept.theory_md, explanations=concept.card_explanations,
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
    )


def is_correct(answer: str, item: StudyItem) -> bool:
    """Grade a chosen answer — a letter, the option text, or a typed numeric value."""
    answer = answer.strip()
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


def settle_answer(
    item_id: int,
    item: StudyItem,
    raw_answer: str,
    elapsed_ms: int,
    tracker,
) -> SettleResult:
    """Settle one answer's log-wide effects: the write path shared by both front
    ends via `StudyLoop`.

    Logs the answer, advances FSRS state, banks quests, records the retry debt,
    and detects personal-best crossings. Session-local framing (streak, combo,
    reward, XP) is *not* here — that is per-session state the StudyLoop owns.
    """
    from engine.config import LEECH_LAPSES
    from engine.quests import settle
    from engine.scheduler import store

    correct, grd = grade(raw_answer, elapsed_ms, item)
    # Read before this answer lands in the log, or it can never beat the record.
    answered_today_before = dao.count_answered_today()
    dao.log_answered(item_id, raw_answer or None, correct, grd, elapsed_ms)

    tracker.refresh()  # re-snapshot baselines if the local day rolled over
    records = tracker.detect(correct, elapsed_ms, answered_today_before)

    new_state = store.apply_rating(store.get_or_create(item.concept_id), grd)
    store.save(new_state)
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
    )


def _days_until(due) -> int | None:
    """Whole days until a card's next review (the 'back in N days' open loop)."""
    if due is None:
        return None
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    d = due if due.tzinfo else due.replace(tzinfo=UTC)
    return max(0, (d - now).days)


def grade(answer: str, elapsed_ms: int, item: StudyItem) -> tuple[bool, int]:
    """Return (is_correct, derived FSRS grade) for an answer — purely data-based.

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
    if item.kind == "recall":
        fast, slow = GRADE_FAST_MS, GRADE_SLOW_MS
    else:
        fast, slow = GRADE_FAST_MS_GEN, GRADE_SLOW_MS_GEN
    return correct, derive_grade(correct, elapsed_ms, fast, slow)
