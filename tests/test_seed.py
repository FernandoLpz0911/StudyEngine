"""Every subject graph loads, with the expected modes and valid prerequisites."""
from engine.db import dao
from engine.subjects import SUBJECTS

EXPECTED_MODE = {
    "diffeq": "generator",
    "databases": "recall",
    "proofs": "recall",
    "econ": "recall",
}


class TestSeed:
    def test_all_subjects_present(self, db):
        assert set(dao.list_subjects()) == set(SUBJECTS)

    def test_each_subject_has_concepts(self, db):
        for subject in SUBJECTS:
            assert len(dao.get_concepts(subject)) >= 4

    def test_modes_match_expectation(self, db):
        for subject, mode in EXPECTED_MODE.items():
            assert all(c.mode == mode for c in dao.get_concepts(subject))

    def test_generator_concepts_have_specs(self, db):
        for c in dao.get_concepts("diffeq"):
            assert c.generator and "kind" in c.generator

    def test_recall_concepts_have_cards(self, db):
        for c in dao.get_concepts("proofs"):
            assert c.card_front and c.card_back

    def test_prerequisites_reference_real_concepts(self, db):
        for subject in SUBJECTS:
            ids = {c.id for c in dao.get_concepts(subject)}
            for c in dao.get_concepts(subject):
                for prereq in c.prerequisites:
                    assert prereq in ids
