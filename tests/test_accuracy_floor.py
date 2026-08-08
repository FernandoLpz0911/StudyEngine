"""The accuracy floor, its coverage backstop, and prerequisite repair.

Three rules that decide what the day is spent on when accuracy has collapsed:
stop widening the syllabus, but never so long that unseen material is stranded,
and repair the foundation a miss actually came from.
"""
from __future__ import annotations

from datetime import timedelta

import engine.subjects  # noqa: F401  (registers the problem generators)
from engine import config
from engine.analytics.pace import coverage_deadline
from engine.db import dao
from engine.scheduler import policy, store


def _log(subject: str, concept_id: str, correct: bool, stage: str = "solo") -> None:
    session_id = dao.create_session(subject)
    item_id = dao.log_shown(
        session_id, concept_id, subject, "recall", correct_answer="x", stage=stage
    )
    dao.log_answered(item_id, "x", correct, 3 if correct else 1, 5000)


def _fill(subject: str, concept_id: str, n: int, correct: bool, stage="solo") -> None:
    """Log `n` answers *and* advance the card, so mastery reads them as real reps."""
    for _ in range(n):
        _log(subject, concept_id, correct, stage)
        state = store.get_or_create(concept_id)
        store.save(store.apply_rating(state, 3 if correct else 1, subject=subject))


class TestAccuracyFloor:
    def test_no_evidence_does_not_block_the_frontier(self, db):
        """A subject with a handful of answers has not demonstrated a problem,
        and the frontier is how it gets any."""
        assert policy._above_accuracy_floor("diffeq")

    def test_low_accuracy_closes_the_frontier(self, db):
        concept = dao.get_concepts("diffeq")[0]
        _fill("diffeq", concept.id, config.AHEAD_WINDOW, correct=False)
        assert not policy._above_accuracy_floor("diffeq")

    def test_high_accuracy_keeps_it_open(self, db):
        concept = dao.get_concepts("diffeq")[0]
        _fill("diffeq", concept.id, config.AHEAD_WINDOW, correct=True)
        assert policy._above_accuracy_floor("diffeq")

    def test_scaffolded_answers_do_not_lift_it(self, db):
        """The floor exists to notice unaided accuracy collapsing; paired answers
        came with a worked example and would hide exactly that."""
        concept = dao.get_concepts("diffeq")[0]
        _fill("diffeq", concept.id, config.AHEAD_WINDOW, correct=False)
        _fill("diffeq", concept.id, config.AHEAD_WINDOW, correct=True, stage="paired")
        assert not policy._above_accuracy_floor("diffeq")

    def test_a_blocked_subject_does_not_freeze_another(self, db):
        """The floor is per subject, so one going badly must not stop the rest."""
        concept = dao.get_concepts("diffeq")[0]
        _fill("diffeq", concept.id, config.AHEAD_WINDOW, correct=False)
        assert not policy._may_introduce("diffeq")
        assert policy._may_introduce("proofs")


class TestCoverageBackstop:
    def test_a_distant_deadline_leaves_the_floor_in_charge(self, db):
        far = dao._local_today() + timedelta(
            days=config.CONSOLIDATION_DAYS + config.COVERAGE_BACKSTOP_DAYS + 30
        )
        dao.set_exam_date("diffeq", far.isoformat())
        assert not policy._coverage_backstop("diffeq")

    def test_a_near_deadline_overrides_the_floor(self, db):
        """Coverage is the one part of readiness that cannot be repaired late,
        so a learner whose accuracy never recovers must not lose the syllabus."""
        near = dao._local_today() + timedelta(days=config.CONSOLIDATION_DAYS + 1)
        dao.set_exam_date("diffeq", near.isoformat())
        assert (coverage_deadline(near) - dao._local_today()).days <= (
            config.COVERAGE_BACKSTOP_DAYS
        )
        concept = dao.get_concepts("diffeq")[0]
        _fill("diffeq", concept.id, config.AHEAD_WINDOW, correct=False)
        assert not policy._above_accuracy_floor("diffeq")
        assert policy._may_introduce("diffeq")  # the backstop carries it

    def test_no_exam_date_means_no_backstop(self, db):
        assert not policy._coverage_backstop("diffeq")


class TestPrereqRepair:
    @staticmethod
    def _pair():
        """A concept with at least one prerequisite, and that prerequisite."""
        for concept in dao.get_concepts("examp"):
            if concept.prerequisites:
                prereq = dao.get_concept(concept.prerequisites[0])
                if prereq is not None:
                    return concept, prereq
        raise AssertionError("seed data has no prerequisite edge")

    def test_a_weaker_prerequisite_is_returned(self, db):
        concept, prereq = self._pair()
        _fill("examp", concept.id, 6, correct=True)
        _fill("examp", prereq.id, 6, correct=False)
        assert policy.prereq_repair(concept) is not None
        assert policy.prereq_repair(concept).id == prereq.id

    def test_a_stronger_prerequisite_is_not_a_detour(self, db):
        """If the foundation is the stronger of the two, the miss belongs to the
        concept and re-testing the prereq practises nothing."""
        concept, prereq = self._pair()
        _fill("examp", concept.id, 6, correct=False)
        _fill("examp", prereq.id, 6, correct=True)
        assert policy.prereq_repair(concept) is None

    def test_a_never_introduced_prerequisite_is_left_to_the_frontier(self, db):
        concept, prereq = self._pair()
        _fill("examp", concept.id, 6, correct=False)
        assert store.get_or_create(prereq.id).reps == 0
        assert policy.prereq_repair(concept) is None

    def test_a_concept_with_no_prerequisites_repairs_nothing(self, db):
        root = next(c for c in dao.get_concepts("examp") if not c.prerequisites)
        _fill("examp", root.id, 6, correct=False)
        assert policy.prereq_repair(root) is None
