"""Readiness/progress metrics for the dashboard."""
from engine.analytics.readiness import (
    mastery_score,
    overall_progress,
    subject_readiness,
)
from engine.db import dao
from engine.scheduler import store
from engine.subjects import SUBJECTS


class TestMasteryScore:
    def test_unseen_is_zero(self):
        assert mastery_score(0, None, 1.0) == 0.0
        assert mastery_score(0, 1.0, 1.0) == 0.0

    def test_no_accuracy_is_zero(self):
        assert mastery_score(5, None, 1.0) == 0.0

    def test_full_mastery(self):
        assert mastery_score(3, 1.0, 1.0, target_reps=3) == 1.0

    def test_accuracy_scales(self):
        assert mastery_score(3, 0.5, 1.0, target_reps=3) == 0.5

    def test_retention_decay_scales(self):
        assert mastery_score(3, 1.0, 0.6, target_reps=3) == 0.6

    def test_rep_confidence_scales(self):
        assert abs(mastery_score(1, 1.0, 1.0, target_reps=3) - 1 / 3) < 1e-9

    def test_clamped_to_unit(self):
        assert mastery_score(10, 1.0, 1.0, target_reps=3) == 1.0


def _simulate_correct(concept_id: str, subject: str, rounds: int = 3) -> None:
    sid = dao.create_session(subject)
    for _ in range(rounds):
        item = dao.log_shown(sid, concept_id, subject, "k", correct_answer="1.000")
        dao.log_answered(item, "1.000", is_correct=True, grade=4, elapsed_ms=2000)
        store.save(store.apply_rating(store.get_or_create(concept_id), 4))


class TestSubjectReadiness:
    def test_fresh_subject_zero(self, db):
        s = subject_readiness("diffeq")
        assert s["readiness"] == 0.0
        assert s["seen"] == 0
        assert s["mastered"] == 0
        assert s["n_concepts"] >= 4

    def test_readiness_rises_after_correct_practice(self, db):
        _simulate_correct("diffeq.separable", "diffeq")
        s = subject_readiness("diffeq")
        assert s["readiness"] > 0.0
        assert s["seen"] >= 1
        concept = next(c for c in s["concepts"] if c["id"] == "diffeq.separable")
        assert concept["mastery"] > 0.0
        assert concept["reps"] == 3


class TestOverallProgress:
    def test_covers_all_subjects(self, db):
        progress = overall_progress(list(SUBJECTS))
        assert len(progress["subjects"]) == len(SUBJECTS)
        assert 0.0 <= progress["combined_readiness"] <= 1.0
