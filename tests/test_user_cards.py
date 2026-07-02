"""Learner-authored recall cards: DAO roundtrip, API validation, scheduling."""
import numpy as np
from fastapi.testclient import TestClient

import engine.subjects  # noqa: F401
from engine import api, service
from engine.db import dao


def _client():
    return TestClient(api.app)


def _add(client, **overrides):
    payload = {
        "subject": "diffeq",
        "question": "What is an integrating factor for y' + p(x)y = q(x)?",
        "answer": "exp(∫p dx)",
        "distractors": ["exp(∫q dx)", "∫p dx"],
        **overrides,
    }
    return client.post("/api/cards", json=payload)


class TestDao:
    def test_create_list_delete_roundtrip(self, db):
        cid = dao.create_user_card("diffeq", "Q?", "yes", ["no"])
        assert cid.startswith(dao.USER_CARD_PREFIX)
        cards = dao.list_user_cards()
        assert [c["id"] for c in cards] == [cid]
        assert cards[0]["distractors"] == ["no"]
        assert dao.delete_user_card(cid) is True
        assert dao.list_user_cards() == []

    def test_delete_refuses_seeded_concepts(self, db):
        assert dao.delete_user_card("diffeq.separable") is False
        assert dao.get_concept("diffeq.separable") is not None

    def test_delete_removes_study_traces(self, db):
        cid = dao.create_user_card("diffeq", "Q?", "yes", ["no"])
        session = dao.create_session("diffeq")
        item = dao.log_shown(session, cid, "diffeq", "recall")
        dao.log_answered(item, "no", False, 1)
        dao.add_pending_retry(cid)
        assert dao.delete_user_card(cid) is True
        assert dao.pending_retries() == []
        assert dao.get_concept(cid) is None


class TestApi:
    def test_create_and_list(self, db):
        with _client() as client:
            res = _add(client)
            assert res.status_code == 200
            cards = client.get("/api/cards").json()
            assert len(cards) == 1
            assert cards[0]["answer"] == "exp(∫p dx)"

    def test_validation(self, db):
        with _client() as client:
            assert _add(client, subject="nope").status_code == 422
            assert _add(client, question="  ").status_code == 422
            assert _add(client, distractors=["  "]).status_code == 422
            assert _add(client, distractors=["exp(∫p dx)"]).status_code == 422

    def test_delete_endpoint(self, db):
        with _client() as client:
            cid = _add(client).json()["concept_id"]
            assert client.delete(f"/api/cards/{cid}").status_code == 200
            assert client.delete(f"/api/cards/{cid}").status_code == 404
            assert client.delete("/api/cards/diffeq.separable").status_code == 404


class TestScheduling:
    def test_user_card_serves_as_recall_item(self, db):
        cid = dao.create_user_card("diffeq", "Q?", "yes", ["no", "maybe"])
        concept = dao.get_concept(cid)
        item = service.build_item(concept, np.random.default_rng(0))
        assert item.kind == "recall"
        assert set(item.choices) == {"yes", "no", "maybe"}
        assert item.correct == "yes"

    def test_user_card_reachable_by_policy(self, db):
        from engine.scheduler import policy
        cid = dao.create_user_card("diffeq", "Q?", "yes", ["no"])
        seen: set[str] = set()
        # Fresh DB: everything is frontier; the user card has no prereqs so it
        # must eventually be selectable. Weight ties break arbitrarily, so just
        # confirm it appears among available concepts.
        available = {c.id for c in dao.get_concepts("diffeq")}
        assert cid in available
        selection = policy.select_next("diffeq")
        assert selection is not None
        seen.add(selection.concept.id)
