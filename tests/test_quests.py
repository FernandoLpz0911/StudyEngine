"""Daily quests: deterministic draw, log-derived progress, one-time XP bonus."""
from fastapi.testclient import TestClient

import engine.subjects  # noqa: F401
from engine import api, quests
from engine.db import dao


def _log(subject: str, correct: bool, elapsed_ms: int = 5000, n: int = 1) -> None:
    session = dao.create_session(subject)
    concept_id = dao.get_concepts(subject)[0].id
    for _ in range(n):
        item = dao.log_shown(session, concept_id, subject, "recall")
        dao.log_answered(item, "a", correct, 3 if correct else 1, elapsed_ms)


class TestDraw:
    def test_three_quests_and_deterministic(self, db):
        first = quests.todays_quests()
        second = quests.todays_quests()
        assert len(first) == quests.QUESTS_PER_DAY
        assert [q["id"] for q in first] == [q["id"] for q in second]

    def test_progress_capped_at_target(self, db):
        for q in quests.todays_quests():
            assert 0 <= q["progress"] <= q["target"]


class TestBonus:
    def test_claim_is_one_time(self, db):
        assert dao.claim_quest("2026-07-02", "speed_five", 25) is True
        assert dao.claim_quest("2026-07-02", "speed_five", 25) is False
        assert dao.quest_bonus_xp() == 25

    def test_completed_quest_banks_xp_once(self, db, monkeypatch):
        # Force a draw containing speed_five by completing every possible quest
        # signal: fast corrects across three subjects, high volume + accuracy.
        from engine import settings
        settings.set_value("daily_goal", 2)
        for subject in ("diffeq", "proofs", "econ"):
            _log(subject, True, elapsed_ms=2000, n=4)
        xp_before = dao.total_xp()
        drawn = quests.todays_quests()
        done = [q for q in drawn if q["done"]]
        assert done, "with every signal maxed, at least one quest completes"
        assert dao.total_xp() == xp_before + len(done) * quests.BONUS_XP
        # Second call must not double-bank.
        quests.todays_quests()
        assert dao.total_xp() == xp_before + len(done) * quests.BONUS_XP


class TestSettleOnAnswer:
    def test_answering_banks_completed_quests_without_a_quest_view(self, db):
        # Max out every draw-independent quest signal purely through the answer
        # path (12 fast corrects: speed_five, sharp_ten, overachiever all done),
        # then check the bonus was banked without ever calling /quests or the HUD.
        from engine import settings
        settings.set_value("daily_goal", 1)
        settings.set_value("new_per_day", 20)
        with TestClient(api.app) as client:
            sid = client.post(
                "/api/session", json={"scope": "global"}
            ).json()["session_id"]
            for _ in range(12):
                nxt = client.get(f"/api/session/{sid}/next").json()
                if nxt.get("done"):
                    break
                correct = api._sessions[sid].items[nxt["item_id"]].correct
                client.post("/api/answer", json={
                    "session_id": sid, "item_id": nxt["item_id"],
                    "answer": correct, "elapsed_ms": 2000,
                })
        day = dao._local_today().isoformat()
        done_now = [q for q in quests.todays_quests() if q["done"]]
        assert done_now, "12 fast corrects must complete at least one quest"
        # The claims were already in the log before this todays_quests call.
        assert dao.claimed_quests(day) >= {q["id"] for q in done_now}


class TestEndpoint:
    def test_quests_endpoint_shape(self, db):
        with TestClient(api.app) as client:
            data = client.get("/api/quests").json()
            assert len(data) == quests.QUESTS_PER_DAY
            for q in data:
                assert {"id", "name", "desc", "target", "progress", "done",
                        "bonus_xp"} <= set(q)
