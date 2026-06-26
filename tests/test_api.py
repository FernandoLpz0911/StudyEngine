"""HTTP API: study loop, progress, map, mnemonic — over the real engine."""
from fastapi.testclient import TestClient

from engine import api
from engine.db import dao


def _client():
    return TestClient(api.app)


class TestSubjects:
    def test_lists_all_subjects(self, db):
        with _client() as client:
            data = client.get("/api/subjects").json()
        keys = {s["key"] for s in data}
        assert {"examp", "examfm", "diffeq", "databases", "proofs", "econ"} <= keys


class TestStudyLoop:
    def test_global_next_and_answer(self, db):
        with _client() as client:
            sid = client.post("/api/session", json={"scope": "global"}).json()["session_id"]
            nxt = client.get(f"/api/session/{sid}/next").json()
            assert nxt["done"] is False
            assert nxt["choices"] and nxt["question"]

            # answer correctly using the server-side stored correct value
            correct = api._sessions[sid].items[nxt["item_id"]].correct
            res = client.post("/api/answer", json={
                "session_id": sid, "item_id": nxt["item_id"],
                "answer": correct, "elapsed_ms": 3000,
            }).json()
            assert res["is_correct"] is True
            assert res["ask_mnemonic"] is False
            assert res["correct_answer"] == correct

    def test_wrong_answer_offers_mnemonic_and_solution(self, db):
        with _client() as client:
            sid = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            nxt = client.get(f"/api/session/{sid}/next").json()
            res = client.post("/api/answer", json={
                "session_id": sid, "item_id": nxt["item_id"],
                "answer": "definitely-wrong", "elapsed_ms": 1000,
            }).json()
            assert res["is_correct"] is False
            assert res["steps"]
            assert res["ask_mnemonic"] is True

    def test_unknown_session_404(self, db):
        with _client() as client:
            assert client.get("/api/session/99999/next").status_code == 404


class TestProgress:
    def test_progress_has_readiness_and_dkt(self, db):
        with _client() as client:
            data = client.get("/api/progress").json()
        assert "combined_readiness" in data
        assert data["dkt"]["active"] is False
        assert len(data["subjects"]) == 6

    def test_subject_progress_has_concept_mastery(self, db):
        with _client() as client:
            data = client.get("/api/progress/examp").json()
        assert data["n_concepts"] == 44
        assert all("displayed" in c for c in data["concepts"])


class TestMnemonic:
    def test_save_mnemonic(self, db):
        with _client() as client:
            res = client.post(
                "/api/mnemonic", json={"concept_id": "diffeq.separable", "text": "sep+int"}
            ).json()
        assert res["ok"] is True
        assert dao.get_mnemonic("diffeq.separable") == "sep+int"
