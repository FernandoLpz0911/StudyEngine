"""service.settle_answer: the one shared answer-settlement path (issue #2)."""
import numpy as np

import engine.subjects  # noqa: F401
from engine import service
from engine.db import dao
from engine.engagement import RecordTracker


def _served(subject: str = "diffeq"):
    """Log a shown item and return (item_id, item) ready to be answered."""
    session = dao.create_session(subject)
    concept = dao.get_concepts(subject)[0]
    rng = np.random.default_rng(0)
    item = service.build_item(concept, rng)
    item_id = service.log_item_shown(session, item)
    return item_id, item


class TestOutcome:
    def test_correct_answer_scores_and_pays_the_retry_debt(self, db):
        item_id, item = _served()
        dao.add_pending_retry(item.concept_id)  # a debt from a past miss
        outcome = service.settle_answer(
            item_id, item, item.correct, 2000,
            RecordTracker.snapshot(), streak_in=0, best_in=0,
            rng=np.random.default_rng(0),
        )
        assert outcome.correct is True
        assert outcome.grade in (2, 3, 4)
        assert outcome.xp > 0
        assert outcome.streak == 1
        assert item.concept_id not in dao.pending_retries()  # debt cleared

    def test_wrong_answer_owes_a_retest_and_resets_the_run(self, db):
        item_id, item = _served()
        outcome = service.settle_answer(
            item_id, item, "definitely-wrong", 1000,
            RecordTracker.snapshot(), streak_in=6, best_in=6,
            rng=np.random.default_rng(0),
        )
        assert outcome.correct is False
        assert outcome.xp == 0
        assert outcome.streak == 0
        assert outcome.best_streak == 6  # session best survives the miss
        assert "×6" in outcome.combo_break  # names the run that was lost
        assert outcome.ask_mnemonic is True  # wrong + no saved hint
        assert item.concept_id in dao.pending_retries()

    def test_a_faster_correct_surfaces_a_record(self, db):
        # A prior slow correct sets the fastest-ms baseline; a snappy correct now
        # must beat it and surface the crossing through the tracker.
        prior_id, prior = _served()
        service.settle_answer(
            prior_id, prior, prior.correct, 8000,
            RecordTracker.snapshot(), streak_in=0, best_in=0,
            rng=np.random.default_rng(0),
        )
        item_id, item = _served()
        outcome = service.settle_answer(
            item_id, item, item.correct, 1500,
            RecordTracker.snapshot(), streak_in=0, best_in=0,
            rng=np.random.default_rng(0),
        )
        assert any("fastest" in r for r in outcome.records)
