"""service.settle_answer: the log-wide Settle path (issue #2, ADR-0002).

Session-local framing (streak/combo/xp) moved to StudyLoop — see test_studyloop.
"""
import numpy as np

import engine.subjects  # noqa: F401
from engine import service
from engine.db import dao
from engine.engagement import RecordTracker


def _served(subject: str = "diffeq", stage: str = "solo"):
    """Log a shown item and return (item_id, item) ready to be answered.

    Defaults to `solo` because that is the only stage that measures anything —
    records, accuracy and time-based grading all ignore scaffolded items, so a
    fixture left on the derived stage would be testing the ladder, not settle.
    """
    session = dao.create_session(subject)
    concept = dao.get_concepts(subject)[0]
    rng = np.random.default_rng(0)
    item = service.build_item(concept, rng, stage=stage)
    item_id = service.log_item_shown(session, item)
    return item_id, item


class TestSettle:
    def test_correct_answer_scores_and_pays_the_retry_debt(self, db):
        item_id, item = _served()
        dao.add_pending_retry(item.concept_id)  # a debt from a past miss
        res = service.settle_answer(
            item_id, item, item.correct, 2000, RecordTracker.snapshot(),
        )
        assert res.correct is True
        assert res.grade in (2, 3, 4)
        assert item.concept_id not in dao.pending_retries()  # debt cleared

    def test_wrong_answer_owes_a_retest(self, db):
        item_id, item = _served()
        res = service.settle_answer(
            item_id, item, "definitely-wrong", 1000, RecordTracker.snapshot(),
        )
        assert res.correct is False
        assert res.ask_mnemonic is True  # wrong + no saved hint
        assert item.concept_id in dao.pending_retries()

    def test_a_faster_correct_surfaces_a_record(self, db):
        # A prior slow correct sets the fastest-ms baseline; a snappy correct now
        # must beat it and surface the crossing through the tracker.
        prior_id, prior = _served()
        service.settle_answer(
            prior_id, prior, prior.correct, 8000, RecordTracker.snapshot(),
        )
        item_id, item = _served()
        res = service.settle_answer(
            item_id, item, item.correct, 1500, RecordTracker.snapshot(),
        )
        assert any("fastest" in r for r in res.records)


class TestStagedSettlement:
    """A study trial is teaching, not evidence — it must not move the schedule
    or the measured accuracy that readiness is built from (ADR-0013)."""

    @staticmethod
    def _served_at(stage: str, subject: str = "diffeq"):
        session = dao.create_session(subject)
        concept = dao.get_concepts(subject)[0]
        item = service.build_item(concept, np.random.default_rng(0), stage=stage)
        return service.log_item_shown(session, item), item

    def test_a_study_trial_leaves_the_schedule_alone(self, db):
        from engine.scheduler import store

        item_id, item = self._served_at("study")
        before = store.get_or_create(item.concept_id)
        service.settle_answer(
            item_id, item, item.correct, 2000, RecordTracker.snapshot(),
        )
        after = store.get_or_create(item.concept_id)
        assert after.reps == before.reps
        assert after.stability == before.stability

    def test_a_paired_answer_does_advance_the_schedule(self, db):
        from engine.scheduler import store

        item_id, item = self._served_at("paired")
        service.settle_answer(
            item_id, item, item.correct, 2000, RecordTracker.snapshot(),
        )
        assert store.get_or_create(item.concept_id).reps == 1

    def test_scaffolded_answers_never_reach_measured_accuracy(self, db):
        for stage in ("study", "paired"):
            item_id, item = self._served_at(stage)
            service.settle_answer(
                item_id, item, item.correct, 2000, RecordTracker.snapshot(),
            )
        concept_id = dao.get_concepts("diffeq")[0].id
        assert dao.get_concept_accuracy(concept_id) is None

    def test_a_solo_answer_is_measured(self, db):
        item_id, item = self._served_at("solo")
        service.settle_answer(
            item_id, item, item.correct, 2000, RecordTracker.snapshot(),
        )
        assert dao.get_concept_accuracy(item.concept_id) == 1.0

    def test_a_study_trial_miss_asks_no_reflection(self, db):
        """The solution was already on screen — "which step lost you" has no
        meaning, and asking trains clicking through the prompt."""
        item_id, item = self._served_at("study")
        res = service.settle_answer(
            item_id, item, "definitely-wrong", 1000, RecordTracker.snapshot(),
        )
        assert res.ask_reflection is False

    def test_a_solo_miss_with_steps_asks_for_one(self, db):
        item_id, item = self._served_at("solo")
        assert len(item.explain) > 1, "fixture needs a multi-step solution"
        res = service.settle_answer(
            item_id, item, "definitely-wrong", 1000, RecordTracker.snapshot(),
        )
        assert res.ask_reflection is True
        dao.record_reflection(item_id, item.concept_id, 2)
        assert dao.step_breakdown(item.concept_id) == {"2": 1}

    def test_not_sure_is_stored_as_its_own_answer(self, db):
        item_id, item = self._served_at("solo")
        service.settle_answer(
            item_id, item, "definitely-wrong", 1000, RecordTracker.snapshot(),
        )
        dao.record_reflection(item_id, item.concept_id, None)
        assert dao.step_breakdown(item.concept_id) == {"unsure": 1}
