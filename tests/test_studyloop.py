"""StudyLoop: the session-local fold layered on canonical Settle (ADR-0002).

Drives the loop directly — no HTTP, no stdin — which is the point of the seam.
"""
import engine.subjects  # noqa: F401
from engine.loop import Done, StudyLoop, Turn


class TestSettleFold:
    def test_correct_builds_streak_and_xp(self, db):
        loop = StudyLoop.start("diffeq", n=5)
        turn = loop.next()
        assert isinstance(turn, Turn)
        out = loop.settle(turn.item_id, turn.item.correct, 2000)
        assert out.correct is True
        assert out.streak == 1
        assert out.xp > 0
        assert loop.xp == out.xp  # per-answer xp folded into the running total
        assert isinstance(out.combo, str)  # tier label (empty until a higher run)

    def test_wrong_resets_run_but_best_survives(self, db):
        loop = StudyLoop.start("diffeq", n=5)
        loop.streak = 6  # simulate a run in progress
        loop.best = 6
        turn = loop.next()
        out = loop.settle(turn.item_id, "definitely-wrong", 1000)
        assert out.correct is False
        assert out.streak == 0
        assert out.best_streak == 6  # session best survives the miss
        assert "×6" in out.combo_break  # names the run that was lost
        # a fresh miss (not itself a retry) owes an in-session re-test
        assert loop.retry_queue[-1][0] == turn.item.concept_id

    def test_budget_exhausts_then_done_closes_session(self, db):
        loop = StudyLoop.start("diffeq", n=1)
        turn = loop.next()
        assert isinstance(turn, Turn)
        loop.settle(turn.item_id, turn.item.correct, 1500)
        step = loop.next()  # budget spent
        assert isinstance(step, Done)
        assert step.summary["answered"] == 1
