"""Objective grading: answer checking, time-derived FSRS grade, recall MC items."""
import numpy as np

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
