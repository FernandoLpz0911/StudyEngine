"""FSRS card state: persistence and rating application (shared by all subjects)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from fsrs import Card as FsrsCard
from fsrs import Rating, Scheduler, State

from engine.config import (
    EARLY_REINFORCEMENT_REPS,
    EXAM_PEAK_RETENTION,
    EXAM_TAPER_DAYS,
    TARGET_RETENTION,
)
from engine.db.connection import get_connection


@lru_cache(maxsize=8)
def _scheduler(
    desired_retention: float, parameters: tuple[float, ...] | None
) -> Scheduler:
    if parameters is None:
        return Scheduler(desired_retention=desired_retention)
    return Scheduler(parameters=parameters, desired_retention=desired_retention)


def desired_retention(days_to_exam: int | None) -> float:
    """Target recall probability, ramped up as an exam approaches (ADR-0009).

    FSRS optimises for the long run and knows nothing about a sitting, so left
    alone it will space a concept to come due after the exam. Raising the target
    shortens every interval, trading extra reviews for everything being fresh on
    the one day it is measured. Linear between the two ends: no cliff where the
    day's review count suddenly doubles.
    """
    if days_to_exam is None or days_to_exam >= EXAM_TAPER_DAYS:
        return TARGET_RETENTION
    if days_to_exam <= 0:
        return EXAM_PEAK_RETENTION
    progress = 1 - days_to_exam / EXAM_TAPER_DAYS
    return TARGET_RETENTION + progress * (EXAM_PEAK_RETENTION - TARGET_RETENTION)


def _current_scheduler(days_to_exam: int | None = None) -> Scheduler:
    """Scheduler using the learner's fitted FSRS weights when a fit exists."""
    from engine.scheduler.optimize import stored_parameters
    return _scheduler(desired_retention(days_to_exam), stored_parameters())


@dataclass
class CardState:
    concept_id: str
    stability: float | None = None
    difficulty: float | None = None
    last_review: datetime | None = None
    due: datetime | None = None
    reps: int = 0
    lapses: int = 0
    step: int | None = None
    state: str = "learning"


def get_or_create(concept_id: str) -> CardState:
    """Load card state from the DB, or a fresh default on first encounter."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM card_state WHERE concept_id = ?", (concept_id,)
        ).fetchone()
    if row is None:
        return CardState(concept_id=concept_id)
    return CardState(
        concept_id=concept_id,
        stability=row["stability"],
        difficulty=row["difficulty"],
        last_review=_parse_dt(row["last_review"]),
        due=_parse_dt(row["due"]),
        reps=row["reps"],
        lapses=row["lapses"],
        step=row["step"],
        state=row["state"],
    )


def apply_rating(
    card_state: CardState,
    rating: int,
    subject: str | None = None,
    count_rep: bool = True,
) -> CardState:
    """Run a py-fsrs review and return the updated card state (not yet persisted).

    `subject` supplies the exam date that tapers the target retention and clamps
    the next review to fall on or before the sitting. `count_rep=False` applies the
    schedule change without advancing `reps` — used by a failed drill, which is
    real evidence of forgetting but must not inflate the rep-confidence term that
    the mastery score (and so the exam target) is built on (ADR-0008).
    """
    days_to_exam = _days_to_exam(subject)
    scheduler = _current_scheduler(days_to_exam)
    updated, _ = scheduler.review_card(_to_fsrs_card(card_state), Rating(rating))
    was_lapse = card_state.state == "review" and Rating(rating) == Rating.Again
    new_reps = card_state.reps + (1 if count_rep else 0)

    due = updated.due
    if new_reps < EARLY_REINFORCEMENT_REPS and due is not None:
        cap = datetime.now(UTC) + timedelta(days=1)
        if due.tzinfo is None:
            cap = datetime.now() + timedelta(days=1)
        due = min(due, cap)
    due = _clamp_to_exam(due, subject, days_to_exam)

    return CardState(
        concept_id=card_state.concept_id,
        stability=updated.stability,
        difficulty=updated.difficulty,
        last_review=updated.last_review,
        due=due,
        reps=new_reps,
        lapses=card_state.lapses + (1 if was_lapse else 0),
        step=updated.step,
        state=updated.state.name.lower(),
    )


def save(card_state: CardState) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO card_state
                (concept_id, stability, difficulty, last_review, due,
                 reps, lapses, step, state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card_state.concept_id,
                card_state.stability,
                card_state.difficulty,
                _fmt_dt(card_state.last_review),
                _fmt_dt(card_state.due),
                card_state.reps,
                card_state.lapses,
                card_state.step,
                card_state.state,
            ),
        )


def _days_to_exam(subject: str | None) -> int | None:
    """Whole days to the subject's sitting, or None when it has no exam date."""
    if subject is None:
        return None
    from engine.db import dao
    exam = dao.get_exam_date(subject)
    if exam is None:
        return None
    return (exam - dao.local_now().date()).days


def _clamp_to_exam(
    due: datetime | None, subject: str | None, days_to_exam: int | None
) -> datetime | None:
    """Never schedule a review for after the last day it could be served.

    A card whose next review falls past the sitting is, for this purpose, a card
    that is never reviewed again — the interval is optimal for remembering it next
    year and useless for remembering it in September (ADR-0009).

    The cutoff is the day *before* the exam, not the exam itself: the gate is
    suppressed from the eve through the end of exam day so the learner sleeps and
    sits it, so a review landing on exam day is one that never happens.
    """
    if due is None or days_to_exam is None or days_to_exam <= 0:
        return due
    now = datetime.now(UTC) if due.tzinfo else datetime.now()
    latest = now + timedelta(days=max(0, days_to_exam - 1))
    return min(due, latest)


def _to_fsrs_card(cs: CardState) -> FsrsCard:
    card = FsrsCard()
    card.state = State[cs.state.capitalize()]
    card.step = cs.step if cs.step is not None else 0
    card.stability = cs.stability
    card.difficulty = cs.difficulty
    if cs.last_review is not None:
        card.last_review = cs.last_review
    if cs.due is not None:
        card.due = cs.due
    return card


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _fmt_dt(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None
