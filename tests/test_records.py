"""Live personal-best detection and combo-break framing."""
from fastapi.testclient import TestClient

import engine.subjects  # noqa: F401
from engine import api
from engine.engagement import combo_break_message, detect_records


def _baselines() -> dict:
    return {"fastest_ms": 5000, "best_day": 40, "longest_run": 8}


class TestDetectRecords:
    def test_faster_correct_is_record(self):
        records = detect_records(_baselines(), 10, True, 3000, 1)
        assert any("fastest" in r for r in records)

    def test_slower_or_wrong_is_not(self):
        assert not detect_records(_baselines(), 10, True, 6000, 1)
        assert not detect_records(_baselines(), 10, False, 1000, 0)

    def test_fastest_fires_once_then_needs_a_faster_one(self):
        baselines = _baselines()
        assert detect_records(baselines, 10, True, 3000, 1)
        assert baselines["fastest_ms"] == 3000  # baseline advanced in place
        assert not detect_records(baselines, 10, True, 3200, 1)
        assert detect_records(baselines, 10, True, 2500, 1)

    def test_first_ever_answer_is_not_a_record(self):
        fresh = {"fastest_ms": None, "best_day": 0, "longest_run": 0}
        assert detect_records(fresh, 0, True, 1000, 1) == []

    def test_longest_run_fires_only_at_the_crossing(self):
        assert any(
            "longest run" in r
            for r in detect_records(_baselines(), 10, True, 6000, 9)
        )
        # One past the crossing (already fired last answer) and below it: silent.
        assert not detect_records(_baselines(), 10, True, 6000, 10)
        assert not detect_records(_baselines(), 10, True, 6000, 8)

    def test_short_runs_never_records(self):
        small = {"fastest_ms": 5000, "best_day": 40, "longest_run": 1}
        assert not any(
            "longest run" in r for r in detect_records(small, 10, True, 6000, 2)
        )

    def test_biggest_day_fires_only_at_the_crossing(self):
        records = detect_records(_baselines(), 40, True, 6000, 1)
        assert any("biggest day" in r for r in records)
        for before in (30, 41, 55):  # below and past the crossing: silent
            assert not any(
                "biggest day" in r
                for r in detect_records(_baselines(), before, True, 6000, 1)
            )


class TestComboBreak:
    def test_below_threshold_silent(self):
        assert combo_break_message(2, 5) == ""

    def test_names_the_lost_run(self):
        assert "×7" in combo_break_message(7, 7)

    def test_mentions_session_best_when_higher(self):
        msg = combo_break_message(4, 12)
        assert "×4" in msg and "×12" in msg


class TestApiFields:
    def test_answer_response_has_records_and_combo_break(self, db):
        with TestClient(api.app) as client:
            sid = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            nxt = client.get(f"/api/session/{sid}/next").json()
            res = client.post("/api/answer", json={
                "session_id": sid, "item_id": nxt["item_id"],
                "answer": "wrong", "elapsed_ms": 1000,
            }).json()
            assert res["records"] == []
            assert res["combo_break"] == ""  # no run to lose yet
