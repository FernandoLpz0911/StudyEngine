"""Personal FSRS parameter fit: log building, gating, persistence, scheduler use."""
import json

from fsrs import Scheduler

import engine.subjects  # noqa: F401
from engine.db import dao
from engine.scheduler import optimize, store


def _log_reviews(n: int, concept_id: str = "diffeq.separable") -> None:
    session = dao.create_session("diffeq")
    for _ in range(n):
        item = dao.log_shown(session, concept_id, "diffeq", "x")
        dao.log_answered(item, "a", True, 3, elapsed_ms=5000)


class TestReviewLogs:
    def test_builds_from_interactions(self, db):
        _log_reviews(3)
        logs = optimize.review_logs()
        assert len(logs) == 3
        assert all(log.rating == 3 for log in logs)
        assert all(log.review_duration == 5000 for log in logs)

    def test_same_concept_shares_card_id(self, db):
        _log_reviews(2)
        logs = optimize.review_logs()
        assert logs[0].card_id == logs[1].card_id


class TestFitGate:
    def test_below_gate_does_not_fit(self, db):
        _log_reviews(3)
        result = optimize.fit()
        assert result["fitted"] is False
        assert result["reviews"] == 3
        assert optimize.stored_parameters() is None

    def test_at_gate_fits_and_persists(self, db, monkeypatch):
        _log_reviews(4)
        monkeypatch.setattr(optimize, "FSRS_MIN_REVIEWS", 4)

        fake_params = list(Scheduler().parameters)
        fake_params[0] = 0.5

        class _FakeOptimizer:
            def __init__(self, logs):
                assert len(logs) == 4

            def compute_optimal_parameters(self, verbose=False):
                return fake_params

        import fsrs.optimizer
        monkeypatch.setattr(fsrs.optimizer, "Optimizer", _FakeOptimizer)
        result = optimize.fit()
        assert result["fitted"] is True
        assert optimize.stored_parameters() == tuple(fake_params)


class TestStoredParameters:
    def test_garbage_falls_back_to_none(self, db):
        dao.set_setting(optimize.PARAMS_KEY, "not-json[")
        assert optimize.stored_parameters() is None

    def test_scheduler_picks_up_fitted_weights(self, db):
        params = list(Scheduler().parameters)
        params[0] = 0.4242
        dao.set_setting(optimize.PARAMS_KEY, json.dumps(params))
        scheduler = store._current_scheduler()
        assert float(scheduler.parameters[0]) == 0.4242

    def test_review_still_works_with_fitted_weights(self, db):
        params = list(Scheduler().parameters)
        params[0] = 0.4242
        dao.set_setting(optimize.PARAMS_KEY, json.dumps(params))
        state = store.apply_rating(store.get_or_create("diffeq.separable"), 3)
        assert state.due is not None
        assert state.reps == 1
