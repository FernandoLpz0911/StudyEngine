"""Objective grading: answer checking, time-derived FSRS grade, recall MC items."""
import numpy as np

from engine import config, service
from engine.db import dao
from engine.grading import derive_grade, grade_answer
from engine.recall.cards import as_question


class TestGradeAnswer:
    def test_exact_string_match(self):
        assert grade_answer("2.000", "2.000")

    def test_numeric_within_tolerance(self):
        assert grade_answer("2.0", "2.000004")
        assert not grade_answer("2.0", "2.5")

    def test_default_tolerance_is_tight(self):
        # The default is deliberately strict (1e-5); wider tolerances are passed
        # explicitly by callers that know the answer's precision (typed answers).
        assert not grade_answer("2.0", "2.0004")
        assert grade_answer("2.0", "2.0004", tolerance=1e-3)

    def test_non_numeric_mismatch_is_false(self):
        assert not grade_answer("", "1.000")
        assert not grade_answer("abc", "1.000")


class TestDeriveGrade:
    def test_incorrect_is_always_again(self):
        assert derive_grade(False, 1000) == 1
        assert derive_grade(False, 999999) == 1

    def test_correct_and_fast_is_easy(self):
        assert derive_grade(True, 3000, fast_ms=8000, slow_ms=30000) == 4

    def test_correct_and_slow_is_hard(self):
        assert derive_grade(True, 40000, fast_ms=8000, slow_ms=30000) == 2

    def test_correct_and_normal_is_good(self):
        assert derive_grade(True, 15000, fast_ms=8000, slow_ms=30000) == 3

    def test_unknown_time_defaults_to_good(self):
        assert derive_grade(True, 0) == 3


class TestAbandonedAnswerTime:
    """A walk away from the desk must not be recorded as a slow recall.

    The client reports active time, but a tab left open overnight still posts
    wall clock — one answer was once logged at 43 hours, which grades Hard and
    drags the concept's interval down for something that was never a struggle.
    """

    def _item(self):
        return service.StudyItem(
            concept_id="gp.axioms", concept_name="Axioms", subject="examp",
            reason="review", kind="test", question="q", choices=[], correct="1",
            explain=[], seed=0, params={},
        )

    def test_grade_is_clamped_before_it_reaches_fsrs(self, db, monkeypatch):
        item = self._item()
        session = dao.create_session("examp")
        item_id = dao.log_shown(session, item.concept_id, "examp", kind="test")

        class _Tracker:
            def refresh(self): pass
            def detect(self, *a): return []

        day_ms = 43 * 60 * 60 * 1000
        result = service.settle_answer(item_id, item, "1", day_ms, _Tracker())
        assert result.correct
        assert result.grade != 1

        logged = dao.graded_reviews()[-1]
        assert logged[3] <= config.MAX_ANSWER_MS, "the log kept the abandoned time"

    def test_an_honest_slow_answer_is_untouched(self):
        # Well inside the ceiling, so clamping cannot rewrite a real struggle.
        honest = 4 * 60 * 1000
        assert honest < config.MAX_ANSWER_MS
        assert derive_grade(True, honest, fast_ms=30000, slow_ms=150000) == 2


class TestRecallQuestion:
    def test_builds_multiple_choice(self, db):
        rng = np.random.default_rng(0)
        concept = dao.get_concept("econ.incentives")
        q = as_question(concept, rng)
        assert q.concept_id == "econ.incentives"
        assert q.correct in q.choices
        assert len(q.choices) == 1 + len(concept.card_distractors)
        assert len(set(q.choices)) == len(q.choices)  # no duplicate options

    def test_correct_option_matches_answer(self, db):
        rng = np.random.default_rng(1)
        concept = dao.get_concept("proofs.induction")
        q = as_question(concept, rng)
        assert q.correct == concept.card_answer
