"""Global interleaved selection across subjects."""
from datetime import UTC, datetime, timedelta

from engine.db import dao
from engine.scheduler import policy, store


def _overdue(concept_id: str) -> None:
    past = datetime.now(UTC) - timedelta(days=2)
    cs = store.get_or_create(concept_id)
    cs.reps = 2
    cs.stability = 8.0
    cs.state = "review"
    cs.last_review = past
    cs.due = past
    store.save(cs)


def _practice(concept_id: str, subject: str, correct: bool, rounds: int = 3) -> None:
    sid = dao.create_session(subject)
    grade = 4 if correct else 1
    for _ in range(rounds):
        item = dao.log_shown(sid, concept_id, subject, "k", correct_answer="1.000")
        dao.log_answered(item, "1.000", correct, grade, 2000)
        store.save(store.apply_rating(store.get_or_create(concept_id), grade))
    past = datetime.now(UTC) - timedelta(days=1)
    cs = store.get_or_create(concept_id)
    cs.last_review = past
    cs.due = past
    store.save(cs)


class TestSelectGlobal:
    def test_fresh_returns_new_concept(self, db):
        sel = policy.select_global(["diffeq", "econ"])
        assert sel is not None
        assert sel.reason == "new"

    def test_interleave_penalty_avoids_last_subject(self, db):
        _overdue("diffeq.intro")
        _overdue("econ.incentives")
        assert policy.select_global(
            ["diffeq", "econ"], avoid_subject="diffeq"
        ).concept.subject == "econ"
        assert policy.select_global(
            ["diffeq", "econ"], avoid_subject="econ"
        ).concept.subject == "diffeq"

    def test_weak_mode_picks_weakest(self, db):
        _practice("diffeq.intro", "diffeq", correct=True)
        _practice("econ.incentives", "econ", correct=False)
        assert policy.select_global(
            ["diffeq", "econ"], mode="weak"
        ).concept.id == "econ.incentives"

    def test_confidence_mode_picks_strongest(self, db):
        _practice("diffeq.intro", "diffeq", correct=True)
        _practice("econ.incentives", "econ", correct=False)
        assert policy.select_global(
            ["diffeq", "econ"], mode="confidence"
        ).concept.id == "diffeq.intro"
