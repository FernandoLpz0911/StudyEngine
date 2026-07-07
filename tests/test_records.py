"""Live personal-best detection and combo-break framing."""
from fastapi.testclient import TestClient

import engine.subjects  # noqa: F401
from engine import api
from engine.engagement import combo_break_message


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
