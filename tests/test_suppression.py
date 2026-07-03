"""Suspend/bury: storage, policy exclusion, prereq unblocking, due count, API."""
from datetime import timedelta

from fastapi.testclient import TestClient

import engine.subjects  # noqa: F401
from engine import api
from engine.db import dao
from engine.scheduler import policy, store
from engine.scheduler.store import CardState


def _client():
    return TestClient(api.app)


class TestStorage:
    def test_suspend_and_resume(self, db):
        dao.suspend_concept("diffeq.separable")
        assert "diffeq.separable" in dao.suppressed_concept_ids()
        assert [s["id"] for s in dao.list_suspended()] == ["diffeq.separable"]
        dao.resume_concept("diffeq.separable")
        assert dao.suppressed_concept_ids() == set()

    def test_bury_expires_next_day(self, db):
        dao.bury_concept("diffeq.separable")
        assert "diffeq.separable" in dao.suppressed_concept_ids()
        tomorrow = dao._local_today() + timedelta(days=1)
        assert "diffeq.separable" not in dao.suppressed_concept_ids(tomorrow)
        assert dao.list_suspended() == []  # buried is not suspended

    def test_suspend_clears_pending_retry(self, db):
        dao.add_pending_retry("diffeq.separable")
        dao.suspend_concept("diffeq.separable")
        assert dao.pending_retries() == []

    def test_suspended_only_set_excludes_buried(self, db):
        dao.suspend_concept("diffeq.separable")
        dao.bury_concept("diffeq.cauchy_euler")
        assert dao.suspended_concept_ids() == {"diffeq.separable"}

    def test_bury_does_not_demote_suspension(self, db):
        dao.suspend_concept("diffeq.separable")
        dao.bury_concept("diffeq.separable")  # must be a no-op
        assert "diffeq.separable" in dao.suspended_concept_ids()
        assert [s["id"] for s in dao.list_suspended()] == ["diffeq.separable"]

    def test_suspending_unseen_concepts_lowers_exam_pace(self, db):
        from datetime import timedelta

        from engine.analytics.readiness import subject_readiness
        dao.set_exam_date(
            "diffeq", (dao._local_today() + timedelta(days=10)).isoformat()
        )
        before = subject_readiness("diffeq")["pace_new_per_day"]
        for concept in dao.get_concepts("diffeq")[:5]:
            dao.suspend_concept(concept.id)
        after = subject_readiness("diffeq")["pace_new_per_day"]
        assert after < before  # unreachable concepts no longer inflate the quota


class TestPolicy:
    def test_suppressed_never_selected(self, db):
        for concept in dao.get_concepts("diffeq"):
            dao.suspend_concept(concept.id)
        assert policy.select_next("diffeq") is None
        assert policy.select_global(["diffeq"]) is None

    def test_suspended_prereq_does_not_block_children(self, db):
        concepts = dao.get_concepts("diffeq")
        child = next(c for c in concepts if c.prerequisites)
        for prereq in child.prerequisites:
            dao.suspend_concept(prereq)
        available_new: set[str] = set()
        # Drain the frontier: each pick is answered so the next differs.
        for _ in range(len(concepts)):
            selection = policy.select_next("diffeq")
            if selection is None:
                break
            available_new.add(selection.concept.id)
            store.save(
                store.apply_rating(store.get_or_create(selection.concept.id), 3)
            )
        assert child.id in available_new

    def test_buried_prereq_does_not_unlock_children(self, db):
        concepts = dao.get_concepts("diffeq")
        child = next(c for c in concepts if c.prerequisites)
        for prereq in child.prerequisites:
            dao.bury_concept(prereq)
        served: set[str] = set()
        for _ in range(len(concepts)):
            selection = policy.select_next("diffeq")
            if selection is None:
                break
            served.add(selection.concept.id)
            store.save(
                store.apply_rating(store.get_or_create(selection.concept.id), 3)
            )
        assert child.id not in served  # bury implies no mastery of the prereq

    def test_retry_queue_skips_suppressed(self, db):
        with _client() as client:
            sid = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            nxt = client.get(f"/api/session/{sid}/next").json()
            client.post("/api/answer", json={
                "session_id": sid, "item_id": nxt["item_id"],
                "answer": "wrong", "elapsed_ms": 1000,
            })
            missed = nxt["concept_id"]
            dao.bury_concept(missed)
            # Drain several next-items: the buried concept must not be served.
            for _ in range(6):
                item = client.get(f"/api/session/{sid}/next").json()
                if item.get("done"):
                    break
                assert item["concept_id"] != missed
                correct = api._sessions[sid].items[item["item_id"]].correct
                client.post("/api/answer", json={
                    "session_id": sid, "item_id": item["item_id"],
                    "answer": correct, "elapsed_ms": 1000,
                })

    def test_due_count_excludes_suppressed(self, db):
        past = "2020-01-01T00:00:00+00:00"
        store.save(CardState(concept_id="diffeq.separable", reps=3, due=None))
        with dao.get_connection() as conn:
            conn.execute(
                "UPDATE card_state SET due = ? WHERE concept_id = ?",
                (past, "diffeq.separable"),
            )
        assert dao.due_count() == 1
        dao.suspend_concept("diffeq.separable")
        assert dao.due_count() == 0


class TestApi:
    def test_suspend_resume_roundtrip(self, db):
        with _client() as client:
            assert client.post(
                "/api/concepts/diffeq.separable/suspend"
            ).status_code == 200
            listed = client.get("/api/concepts/suspended").json()
            assert [s["id"] for s in listed] == ["diffeq.separable"]
            assert client.post(
                "/api/concepts/diffeq.separable/resume"
            ).status_code == 200
            assert client.get("/api/concepts/suspended").json() == []

    def test_unknown_concept_404(self, db):
        with _client() as client:
            assert client.post("/api/concepts/nope/suspend").status_code == 404
            assert client.post("/api/concepts/nope/bury").status_code == 404
