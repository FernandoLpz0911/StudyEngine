"""Data-based readiness/progress metrics for the dashboard.

A concept's mastery blends three measured signals — never self-reported:
  - accuracy: measured fraction-correct on recent attempts,
  - retention: current FSRS recall probability (decays as a review goes overdue),
  - confidence: how many times it has been reviewed, capped at MASTERY_TARGET_REPS.

Subject readiness is the exam-weight-weighted average of concept mastery.
"""
from __future__ import annotations

from datetime import UTC, datetime

from engine.config import (
    MASTERY_ACCURACY_WINDOW,
    MASTERY_TARGET_REPS,
    MASTERY_THRESHOLD,
)
from engine.db import dao
from engine.scheduler import store
from engine.scheduler.fsrs_core import retrievability
from engine.scheduler.store import CardState


def mastery_score(
    reps: int,
    accuracy: float | None,
    retention: float,
    target_reps: int = MASTERY_TARGET_REPS,
) -> float:
    """Combine measured accuracy, FSRS retention, and rep-confidence into [0, 1]."""
    if reps <= 0 or accuracy is None:
        return 0.0
    confidence = min(1.0, reps / target_reps)
    return max(0.0, min(1.0, accuracy * retention * confidence))


def _retention_now(cs: CardState, now: datetime) -> float:
    """Current recall probability from FSRS; 0.5 prior before stability is known."""
    if cs.stability and cs.last_review:
        last = cs.last_review
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        elapsed = max(0.0, (now - last).total_seconds() / 86400)
        return retrievability(elapsed, cs.stability)
    return 0.5


def concept_mastery(concept_id: str, now: datetime | None = None) -> float:
    now = now or datetime.now(UTC)
    cs = store.get_or_create(concept_id)
    accuracy = dao.get_concept_accuracy(concept_id, window=MASTERY_ACCURACY_WINDOW)
    return mastery_score(cs.reps, accuracy, _retention_now(cs, now))


def subject_readiness(subject: str) -> dict:
    """Per-concept mastery plus the exam-weighted readiness for one subject."""
    concepts = dao.get_concepts(subject)
    now = datetime.now(UTC)

    rows = []
    weight_sum = 0.0
    weighted_mastery = 0.0
    for concept in concepts:
        cs = store.get_or_create(concept.id)
        mastery = concept_mastery(concept.id, now)
        due = (
            cs.reps > 0
            and cs.due is not None
            and _aware(cs.due) <= now
        )
        rows.append({
            "id": concept.id,
            "name": concept.name,
            "mode": concept.mode,
            "mastery": round(mastery, 3),
            "reps": cs.reps,
            "due": due,
        })
        weight_sum += concept.exam_weight
        weighted_mastery += concept.exam_weight * mastery

    readiness = weighted_mastery / weight_sum if weight_sum else 0.0
    stats = dao.subject_stats(subject)
    return {
        "subject": subject,
        "readiness": round(readiness, 3),
        "n_concepts": len(concepts),
        "seen": sum(1 for r in rows if r["reps"] > 0),
        "mastered": sum(1 for r in rows if r["mastery"] >= MASTERY_THRESHOLD),
        "due": sum(1 for r in rows if r["due"]),
        "answered": stats["answered"],
        "accuracy": stats["accuracy"],
        "concepts": rows,
    }


def overall_progress(subjects: list[str]) -> dict:
    """Readiness summary for every subject plus a combined, concept-weighted figure."""
    per_subject = [subject_readiness(s) for s in subjects]
    total_concepts = sum(s["n_concepts"] for s in per_subject)
    combined = (
        sum(s["readiness"] * s["n_concepts"] for s in per_subject) / total_concepts
        if total_concepts
        else 0.0
    )
    return {"combined_readiness": round(combined, 3), "subjects": per_subject}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
