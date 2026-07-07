"""RecordTracker: log-wide record run + crossing detection (issue #1)."""
import engine.subjects  # noqa: F401
from engine.db import dao
from engine.engagement import RecordTracker


def _log_correct_run(subject: str, n: int, elapsed_ms: int = 6000) -> None:
    """Append n consecutive correct answers to the interaction log."""
    session = dao.create_session(subject)
    concept_id = dao.get_concepts(subject)[0].id
    for _ in range(n):
        item = dao.log_shown(session, concept_id, subject, "recall")
        dao.log_answered(item, "a", True, 3, elapsed_ms)


def _tracker(fastest=5000, best_day=40, longest_run=8, run=0) -> RecordTracker:
    return RecordTracker(
        fastest_ms=fastest, best_day=best_day, longest_run=longest_run, run=run,
    )


class TestDetect:
    def test_faster_correct_is_a_record(self):
        records = _tracker().detect(correct=True, elapsed_ms=3000, answered_today_before=10)
        assert any("fastest" in r for r in records)

    def test_slower_or_wrong_is_not_a_record(self):
        assert not _tracker().detect(correct=True, elapsed_ms=6000, answered_today_before=10)
        assert not _tracker().detect(correct=False, elapsed_ms=1000, answered_today_before=10)

    def test_fastest_fires_once_then_needs_a_strictly_faster_one(self):
        t = _tracker()
        assert t.detect(correct=True, elapsed_ms=3000, answered_today_before=10)
        assert not t.detect(correct=True, elapsed_ms=3200, answered_today_before=10)
        assert t.detect(correct=True, elapsed_ms=2500, answered_today_before=10)

    def _longest(self, records: list[str]) -> bool:
        return any("longest run" in r for r in records)

    def test_longest_run_fires_at_the_crossing_then_stays_silent(self):
        t = _tracker(longest_run=8, run=8)  # one past the current best
        assert self._longest(t.detect(True, 6000, 10))  # run 9 — new record
        assert not self._longest(t.detect(True, 6000, 10))  # run 10 — silent
        assert not self._longest(t.detect(True, 6000, 10))  # run 11 — silent

    def test_short_runs_never_record(self):
        t = _tracker(longest_run=1, run=1)
        assert not self._longest(t.detect(True, 6000, 10))  # run 2, below floor

    def test_ended_run_banks_its_peak_and_blocks_stale_crossings(self):
        t = _tracker(longest_run=8, run=8)
        assert self._longest(t.detect(True, 6000, 10))  # crossing at 9
        for _ in range(11):  # climb to 20, all silent
            assert not self._longest(t.detect(True, 6000, 10))
        t.detect(False, 6000, 10)  # run ends — peak of 20 banked
        for _ in range(9):  # a later run back up to the old ×9 crossing
            assert not self._longest(t.detect(True, 6000, 10))
        for _ in range(11):  # ...climbs to 20, still silent
            t.detect(True, 6000, 10)
        assert self._longest(t.detect(True, 6000, 10))  # run 21 — genuine new record

    def test_biggest_day_fires_only_at_the_crossing(self):
        assert any(
            "biggest day" in r
            for r in _tracker(best_day=40).detect(True, 6000, answered_today_before=40)
        )
        for before in (30, 41, 55):  # below and past the crossing: silent
            assert not any(
                "biggest day" in r
                for r in _tracker(best_day=40).detect(True, 6000, before)
            )

    def test_first_ever_answer_is_not_a_record(self):
        fresh = _tracker(fastest=None, best_day=0, longest_run=0, run=0)
        assert fresh.detect(True, 1000, answered_today_before=0) == []


class TestSnapshot:
    def test_seeds_the_run_from_the_logs_trailing_correct_count(self, db):
        # A run of 4 correct is both the all-time best and the trailing run. If
        # snapshot seeds the current run from it, a single further correct answer
        # crosses to ×5 — proof the run continues across the session boundary
        # instead of restarting at zero (issue #1 / finding #3).
        _log_correct_run("diffeq", 4)
        tracker = RecordTracker.snapshot()
        records = tracker.detect(True, 6000, answered_today_before=4)
        assert any("longest run — ×5" in r for r in records)

    def test_a_broken_trailing_run_seeds_zero(self, db):
        _log_correct_run("diffeq", 4)
        session = dao.create_session("diffeq")
        concept_id = dao.get_concepts("diffeq")[0].id
        item = dao.log_shown(session, concept_id, "diffeq", "recall")
        dao.log_answered(item, "z", False, 1, 6000)  # a wrong answer ends the run
        tracker = RecordTracker.snapshot()
        # One correct now is run 1, nowhere near the banked best of 4 — silent.
        assert not any(
            "longest run" in r for r in tracker.detect(True, 6000, 5)
        )
