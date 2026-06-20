"""Recall flashcards and generator-answer grading."""
from engine.db import dao
from engine.grading import grade_answer
from engine.recall.cards import as_flashcard


class TestGrading:
    def test_exact_string_match(self):
        assert grade_answer("2.000", "2.000")

    def test_numeric_within_tolerance(self):
        assert grade_answer("2.0", "2.0004")
        assert not grade_answer("2.0", "2.5")

    def test_non_numeric_mismatch_is_false(self):
        assert not grade_answer("", "1.000")
        assert not grade_answer("abc", "1.000")


class TestRecall:
    def test_flashcard_from_recall_concept(self, db):
        concept = dao.get_concept("econ.incentives")
        card = as_flashcard(concept)
        assert card.concept_id == "econ.incentives"
        assert "incentive" in card.front.lower()
        assert card.back

    def test_flashcard_fallback_front(self, db):
        concept = dao.get_concept("proofs.induction")
        card = as_flashcard(concept)
        assert card.front and card.back
