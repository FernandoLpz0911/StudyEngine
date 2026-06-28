"""Every subject graph loads, with the expected modes and valid prerequisites."""
from engine.db import dao
from engine.subjects import SUBJECTS

# Every subject now has generator concepts; these carry concept cards too.
MIXED_SUBJECTS = ("databases", "proofs", "econ", "diffeq")


class TestSeed:
    def test_all_subjects_present(self, db):
        assert set(dao.list_subjects()) == set(SUBJECTS)

    def test_each_subject_has_concepts(self, db):
        for subject in SUBJECTS:
            assert len(dao.get_concepts(subject)) >= 4

    def test_diffeq_has_generator_drills(self, db):
        modes = {c.mode for c in dao.get_concepts("diffeq")}
        assert "generator" in modes  # the auto-graded drills remain

    def test_mixed_subjects_have_both_modes(self, db):
        for subject in MIXED_SUBJECTS:
            modes = {c.mode for c in dao.get_concepts(subject)}
            assert modes == {"generator", "recall"}

    def test_generator_concepts_have_specs(self, db):
        for subject in SUBJECTS:
            for c in dao.get_concepts(subject):
                if c.mode == "generator":
                    assert c.generator and "kind" in c.generator

    def test_recall_concepts_have_objective_cards(self, db):
        for subject in SUBJECTS:
            for c in dao.get_concepts(subject):
                if c.mode == "recall":
                    assert c.card_question and c.card_answer
                    assert len(c.card_distractors) >= 2
                    assert c.card_answer not in c.card_distractors

    def test_prerequisites_reference_real_concepts(self, db):
        for subject in SUBJECTS:
            ids = {c.id for c in dao.get_concepts(subject)}
            for c in dao.get_concepts(subject):
                for prereq in c.prerequisites:
                    assert prereq in ids
