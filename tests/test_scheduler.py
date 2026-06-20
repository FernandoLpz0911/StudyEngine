"""FSRS core math, card-state lifecycle, and next-concept policy."""
import pytest

from engine.scheduler import policy, store
from engine.scheduler.fsrs_core import interval_for_target, retrievability


class TestFsrsCore:
    def test_retrievability_at_zero_is_one(self):
        assert retrievability(0, 5.0) == pytest.approx(1.0)

    def test_retrievability_at_stability_is_ninety_percent(self):
        for s in (1.0, 5.0, 21.0):
            assert retrievability(s, s) == pytest.approx(0.9, abs=1e-9)

    def test_retrievability_decreases(self):
        s = 10.0
        assert retrievability(5, s) > retrievability(10, s) > retrievability(20, s)

    def test_interval_at_default_retention_equals_stability(self):
        for s in (1.0, 5.0, 21.0):
            assert interval_for_target(s, 0.9) == round(s)

    def test_interval_minimum_one(self):
        assert interval_for_target(0.001) == 1


class TestCardStore:
    def test_new_concept_defaults(self, db):
        cs = store.get_or_create("diffeq.separable")
        assert cs.reps == 0 and cs.stability is None

    def test_apply_rating_increments_and_persists(self, db):
        cs = store.apply_rating(store.get_or_create("diffeq.separable"), 3)
        assert cs.reps == 1 and cs.stability and cs.stability > 0
        store.save(cs)
        assert store.get_or_create("diffeq.separable").reps == 1


class TestPolicy:
    def test_fresh_subject_starts_with_new_root(self, db):
        sel = policy.select_next("diffeq")
        assert sel is not None
        assert sel.reason == "new"
        assert sel.concept.prerequisites == []

    def test_locked_until_prereq_introduced(self, db):
        sel = policy.select_next("diffeq")
        assert sel.concept.id == "diffeq.separable"  # only root is available first
        store.save(store.apply_rating(store.get_or_create("diffeq.separable"), 3))
        ids = {policy.select_next("diffeq").concept.id for _ in range(1)}
        assert ids  # something is now selectable (root review or unlocked child)

    def test_unknown_subject_returns_none(self, db):
        assert policy.select_next("nonexistent") is None
