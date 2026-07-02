"""FSRS card state: persistence and rating application (shared by all subjects)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from fsrs import Card as FsrsCard
from fsrs import Rating, Scheduler, State

from engine.config import EARLY_REINFORCEMENT_REPS, TARGET_RETENTION
from engine.db.connection import get_connection


@lru_cache(maxsize=8)
def _scheduler(
    desired_retention: float, parameters: tuple[float, ...] | None
) -> Scheduler:
    if parameters is None:
        return Scheduler(desired_retention=desired_retention)
    return Scheduler(parameters=parameters, desired_retention=desired_retention)


def _current_scheduler() -> Scheduler:
    """Scheduler using the learner's fitted FSRS weights when a fit exists."""
    from engine.scheduler.optimize import stored_parameters
    return _scheduler(TARGET_RETENTION, stored_parameters())


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


def apply_rating(card_state: CardState, rating: int) -> CardState:
    """Run a py-fsrs review and return the updated card state (not yet persisted)."""
    scheduler = _current_scheduler()
    updated, _ = scheduler.review_card(_to_fsrs_card(card_state), Rating(rating))
    was_lapse = card_state.state == "review" and Rating(rating) == Rating.Again
    new_reps = card_state.reps + 1

    due = updated.due
    if new_reps < EARLY_REINFORCEMENT_REPS and due is not None:
        cap = datetime.now(UTC) + timedelta(days=1)
        if due.tzinfo is None:
            cap = datetime.now() + timedelta(days=1)
        due = min(due, cap)

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
