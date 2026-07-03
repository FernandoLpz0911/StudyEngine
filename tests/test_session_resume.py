"""Session resume: API sessions rebuild from the database after a restart."""
from fastapi.testclient import TestClient

import engine.subjects  # noqa: F401
from engine import api


def _client():
    return TestClient(api.app)


def _answer(client, sid: int, nxt: dict, correct: bool) -> dict:
    answer = api._sessions[sid].items[nxt["item_id"]].correct if correct else "wrong"
    return client.post("/api/answer", json={
        "session_id": sid, "item_id": nxt["item_id"],
        "answer": answer, "elapsed_ms": 2000,
    }).json()


class TestRebuild:
    def test_next_survives_restart(self, db):
        with _client() as client:
            sid = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            nxt = client.get(f"/api/session/{sid}/next").json()
            _answer(client, sid, nxt, correct=True)

            api._sessions.clear()  # simulate a server restart
            res = client.get(f"/api/session/{sid}/next")
            assert res.status_code == 200
            assert res.json()["done"] is False

    def test_state_restored_from_log(self, db):
        with _client() as client:
            sid = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            nxt = client.get(f"/api/session/{sid}/next").json()
            first = _answer(client, sid, nxt, correct=True)
            assert first["is_correct"] is True
            xp_live = api._sessions[sid].xp_session

            api._sessions.clear()
            client.get(f"/api/session/{sid}/next")
            sess = api._sessions[sid]
            assert sess.recent == [True]
            assert sess.streak == 1
            assert sess.best_streak == 1
            assert sess.xp_session == xp_live
            assert sess.scope == "diffeq"
            assert sess.index >= 2  # one answered + one just served

    def test_unanswered_item_lost_but_session_continues(self, db):
        with _client() as client:
            sid = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            nxt = client.get(f"/api/session/{sid}/next").json()

            api._sessions.clear()  # restart before answering
            res = client.post("/api/answer", json={
                "session_id": sid, "item_id": nxt["item_id"],
                "answer": "a", "elapsed_ms": 1000,
            })
            assert res.status_code == 404  # item gone; session itself rebuilt
            assert sid in api._sessions
            assert client.get(f"/api/session/{sid}/next").status_code == 200

    def test_unknown_session_still_404(self, db):
        with _client() as client:
            assert client.get("/api/session/424242/next").status_code == 404

    def test_done_summary_closes_the_session(self, db):
        from engine import settings
        from engine.db import dao
        settings.set_value("new_per_day", 1)
        with _client() as client:
            sid = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            for _ in range(4):  # answer the one new item, then hit done
                nxt = client.get(f"/api/session/{sid}/next").json()
                if nxt.get("done"):
                    break
                correct = api._sessions[sid].items[nxt["item_id"]].correct
                client.post("/api/answer", json={
                    "session_id": sid, "item_id": nxt["item_id"],
                    "answer": correct, "elapsed_ms": 1000,
                })
            assert dao.get_session(sid)["ended_at"] is not None
            # After a restart, the finished session must not resurrect.
            api._sessions.clear()
            assert client.get(f"/api/session/{sid}/next").status_code == 404

    def test_ended_session_is_not_resurrected(self, db):
        from engine.db import dao
        with _client() as client:
            sid = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            dao.close_session(sid)
            api._sessions.clear()
            assert client.get(f"/api/session/{sid}/next").status_code == 404
