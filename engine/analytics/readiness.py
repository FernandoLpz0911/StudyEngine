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
    ENDOWED_BASELINE,
    MASTERY_ACCURACY_WINDOW,
    MASTERY_TARGET_REPS,
    MASTERY_THRESHOLD,
)
from engine.db import dao
from engine.scheduler import store
from engine.scheduler.availability import introduced, is_due
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


def _retention_now(cs: CardState, now: datetime, since: datetime | None = None) -> float:
    """Current recall probability from FSRS; 0.5 prior before stability is known.

    `since` overrides the decay origin. Readiness measures decay from the last
    *unaided* answer (ADR-0014), not from the last review of any kind: FSRS is
    right to reset its clock whenever a card is seen, but a guided review
    demonstrated nothing about unaided recall, and crediting it let a run of
    worked examples walk the projected score up on its own — +1.4 marks across
    18 concepts, measured.
    """
    if cs.stability and (origin := (since or cs.last_review)):
        if origin.tzinfo is None:
            origin = origin.replace(tzinfo=UTC)
        elapsed = max(0.0, (now - origin).total_seconds() / 86400)
        return retrievability(elapsed, cs.stability)
    return 0.5


def unaided_retention(concept_id: str, cs: CardState, now: datetime) -> float:
    """Recall probability credited only as far as the last unaided answer.

    A concept never answered unaided has demonstrated nothing to decay from, so
    it scores zero rather than the 0.5 prior — the prior exists for a card whose
    stability is unknown, not for one whose learner has never been tested on it.
    """
    last_solo = dao.last_solo_review(concept_id)
    if last_solo is None:
        return 0.0
    return _retention_now(cs, now, since=last_solo)


def concept_mastery(concept_id: str, now: datetime | None = None) -> float:
    """Measured competence, unaided in all three factors (ADR-0014).

    Accuracy, retention *and* rep-confidence all read solo evidence only. Leaving
    any one of them scaffolded makes mastery "unaided except in the term nobody is
    looking at" — which is exactly how the retention hole survived the first pass.
    Guided work is credited by [[ascent]] instead; mastery's whole job now is to
    answer readiness questions (rest this concept? drill it? count it mastered?),
    and every one of those must be answered by unaided evidence.
    """
    now = now or datetime.now(UTC)
    cs = store.get_or_create(concept_id)
    accuracy = dao.get_concept_accuracy(concept_id, window=MASTERY_ACCURACY_WINDOW)
    return mastery_score(
        dao.solo_reps(concept_id), accuracy, unaided_retention(concept_id, cs, now)
    )


def mastery_bar(concept_id: str, subject: str) -> float:
    """The mastery a concept must reach to count as mastered, given its reach.

    Not one flat threshold for a leaf and a gateway alike: a foundation carries
    every concept above it, so the standard scales with downstream reach the same
    way the teaching ladder's accuracy bar does (ADR-0013). `MASTERY_THRESHOLD`
    stays the floor, so nothing gets an easier bar than before.
    """
    from engine.service import concept_reach
    from engine.teaching import required_accuracy

    reach = concept_reach(subject).get(concept_id, 0)
    return max(MASTERY_THRESHOLD, required_accuracy(reach))


def subject_readiness(subject: str) -> dict:
    """Per-concept mastery plus the exam-weighted readiness for one subject."""
    concepts = dao.get_concepts(subject)
    now = datetime.now(UTC)
    suppressed = dao.suppressed_concept_ids()

    rows = []
    weight_sum = 0.0
    weighted_mastery = 0.0
    for concept in concepts:
        cs = store.get_or_create(concept.id)
        mastery = concept_mastery(concept.id, now)
        # Endowed progress: the displayed value never drops below the baseline,
        # so the map glows faintly from the start rather than reading 0%.
        displayed = max(mastery, ENDOWED_BASELINE)
        due = is_due(cs.reps, cs.due, now, concept.id in suppressed)
        rows.append({
            "id": concept.id,
            "name": concept.name,
            "mode": concept.mode,
            "mastery": round(mastery, 3),
            "displayed": round(displayed, 3),
            "reps": cs.reps,
            "due": due,
        })
        weight_sum += concept.exam_weight
        weighted_mastery += concept.exam_weight * displayed

    readiness = weighted_mastery / weight_sum if weight_sum else 0.0
    stats = dao.subject_stats(subject)
    seen = sum(1 for r in rows if r["reps"] > 0)
    # Exam pace only counts concepts the policy can still serve: an indefinitely
    # suspended never-studied concept is not coverable and must not inflate the
    # daily quota (symmetric with policy treating suspended prereqs as introduced).
    suspended = dao.suspended_concept_ids()
    coverable_unseen = sum(
        1 for c, r in zip(concepts, rows, strict=True)
        if not introduced(r["reps"], c.id in suspended)
    )
    return {
        "subject": subject,
        "domain": concepts[0].domain if concepts else None,
        "readiness": round(readiness, 3),
        "n_concepts": len(concepts),
        "seen": seen,
        "mastered": sum(
            1 for r in rows if r["mastery"] >= mastery_bar(r["id"], subject)
        ),
        "due": sum(1 for r in rows if r["due"]),
        "answered": stats["answered"],
        "accuracy": stats["accuracy"],
        **_exam_countdown(subject, coverable_unseen),
        "concepts": rows,
    }


def _exam_countdown(subject: str, unseen: int) -> dict:
    """Deadline framing: days to the exam and the new-concept pace it implies.

    A visible per-day pace turns an abstract syllabus into a daily quota — and an
    approaching exam date is the honest urgency no synthetic streak can match.
    """
    exam = dao.get_exam_date(subject)
    if exam is None:
        return {"exam_date": None, "days_left": None, "pace_new_per_day": None}
    # Same local-day boundary as streaks/goals, so the countdown flips at the
    # learner's midnight rather than UTC's.
    days_left = (exam - dao._local_today()).days
    pace = None
    if days_left > 0 and unseen > 0:
        pace = round(unseen / days_left, 1)
    return {
        "exam_date": exam.isoformat(),
        "days_left": days_left,
        "pace_new_per_day": pace,
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
