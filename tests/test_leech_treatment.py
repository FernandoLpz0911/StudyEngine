"""Leech intervention: flag on served items, forced mnemonic ask on correct."""
from fastapi.testclient import TestClient

import engine.subjects  # noqa: F401
from engine import api
from engine.config import LEECH_LAPSES
from engine.db import dao
from engine.scheduler import store
from engine.scheduler.store import CardState


def _client():
    return TestClient(api.app)


def _make_leech(concept_id: str) -> None:
    store.save(CardState(concept_id=concept_id, reps=5, lapses=LEECH_LAPSES))


class TestLapses:
    def test_unseen_concept_has_zero(self, db):
        assert dao.get_lapses("diffeq.separable") == 0

    def test_reads_card_state(self, db):
        _make_leech("diffeq.separable")
        assert dao.get_lapses("diffeq.separable") == LEECH_LAPSES


class TestServedItemFlags:
    def test_leech_flag_and_lapses_served(self, db):
        with _client() as client:
            sid = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            nxt = client.get(f"/api/session/{sid}/next").json()
            assert nxt["leech"] is False

            _make_leech(nxt["concept_id"])
            nxt2 = client.get(f"/api/session/{sid}/next").json()
            leech_item = nxt2 if nxt2["concept_id"] else nxt2
            assert "leech" in leech_item and "lapses" in leech_item


class TestMnemonicAsk:
    def test_correct_leech_without_note_asks(self, db):
        with _client() as client:
            sid = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            nxt = client.get(f"/api/session/{sid}/next").json()
            _make_leech(nxt["concept_id"])
            correct = api._sessions[sid].items[nxt["item_id"]].correct
            res = client.post("/api/answer", json={
                "session_id": sid, "item_id": nxt["item_id"],
                "answer": correct, "elapsed_ms": 2000,
            }).json()
            assert res["is_correct"] is True
            assert res["ask_mnemonic"] is True  # leech: reformulate even when right

    def test_correct_non_leech_does_not_ask(self, db):
        with _client() as client:
            sid = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            nxt = client.get(f"/api/session/{sid}/next").json()
            correct = api._sessions[sid].items[nxt["item_id"]].correct
            res = client.post("/api/answer", json={
                "session_id": sid, "item_id": nxt["item_id"],
                "answer": correct, "elapsed_ms": 2000,
            }).json()
            assert res["ask_mnemonic"] is False

    def test_leech_with_saved_note_not_asked(self, db):
        with _client() as client:
            sid = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            nxt = client.get(f"/api/session/{sid}/next").json()
            _make_leech(nxt["concept_id"])
            dao.save_mnemonic(nxt["concept_id"], "already have one")
            correct = api._sessions[sid].items[nxt["item_id"]].correct
            res = client.post("/api/answer", json={
                "session_id": sid, "item_id": nxt["item_id"],
                "answer": correct, "elapsed_ms": 2000,
            }).json()
            assert res["ask_mnemonic"] is False
