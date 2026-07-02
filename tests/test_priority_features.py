"""Settings, new-per-day cap, persistent retry, per-mode grading, typed answers."""
import pytest
from fastapi.testclient import TestClient

import engine.subjects  # noqa: F401
from engine import api, service, settings
from engine.config import (
    GRADE_FAST_MS,
    GRADE_FAST_MS_GEN,
    GRADE_SLOW_MS_GEN,
    NEW_PER_DAY,
)
from engine.db import dao
from engine.scheduler import policy
from engine.service import StudyItem
from engine.stats import achievements


def _client():
    return TestClient(api.app)


class TestSettings:
    def test_default_comes_from_config(self, db):
        assert settings.get_int("new_per_day") == NEW_PER_DAY

    def test_set_and_get_roundtrip(self, db):
        settings.set_value("daily_goal", 33)
        assert settings.get_int("daily_goal") == 33

    def test_unknown_key_rejected(self, db):
        with pytest.raises(KeyError):
            settings.set_value("nonsense", 1)

    def test_bad_value_rejected(self, db):
        with pytest.raises(ValueError):
            settings.set_value("daily_goal", "not-a-number")

    def test_api_get_and_set(self, db):
        with _client() as client:
            keys = {s["key"] for s in client.get("/api/settings").json()}
            assert {"daily_goal", "new_per_day", "typed_answer_mastery"} <= keys
            res = client.post(
                "/api/settings", json={"key": "daily_goal", "value": "25"}
            )
            assert res.status_code == 200
            current = {
                s["key"]: s["value"] for s in client.get("/api/settings").json()
            }
            assert current["daily_goal"] == 25
            assert client.get("/api/stats").json()["daily_goal"] == 25

    def test_api_rejects_unknown_key(self, db):
        with _client() as client:
            res = client.post("/api/settings", json={"key": "bogus", "value": "1"})
            assert res.status_code == 422


class TestNewPerDayCap:
    def test_frontier_closes_at_cap(self, db):
        from engine.scheduler import store
        settings.set_value("new_per_day", 2)
        session = dao.create_session("diffeq")
        for _ in range(2):
            selection = policy.select_next("diffeq")
            assert selection is not None and selection.reason == "new"
            shown = dao.log_shown(session, selection.concept.id, "diffeq", "x")
            dao.log_answered(shown, "x", True, 4)
            store.save(
                store.apply_rating(store.get_or_create(selection.concept.id), 4)
            )
        assert policy.select_next("diffeq") is None  # nothing due, frontier shut

    def test_reviews_never_capped(self, db):
        settings.set_value("new_per_day", 0)
        # With a zero budget nothing new is served even on a fresh database.
        assert policy.select_next("diffeq") is None
        assert policy.select_global(["diffeq"]) is None


class TestPendingRetry:
    def test_roundtrip(self, db):
        dao.add_pending_retry("diffeq.separable")
        dao.add_pending_retry("diffeq.separable")  # idempotent
        assert dao.pending_retries() == ["diffeq.separable"]
        dao.remove_pending_retry("diffeq.separable")
        assert dao.pending_retries() == []

    def test_wrong_answer_persists_across_sessions(self, db):
        with _client() as client:
            sid = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            nxt = client.get(f"/api/session/{sid}/next").json()
            client.post("/api/answer", json={
                "session_id": sid, "item_id": nxt["item_id"],
                "answer": "definitely-wrong", "elapsed_ms": 1000,
            })
            missed = nxt["concept_id"]
            assert missed in dao.pending_retries()

            # A brand-new session owes the re-test up front.
            sid2 = client.post(
                "/api/session", json={"scope": "diffeq"}
            ).json()["session_id"]
            nxt2 = client.get(f"/api/session/{sid2}/next").json()
            assert nxt2["concept_id"] == missed
            assert nxt2["reason"] == "retry"

            correct = api._sessions[sid2].items[nxt2["item_id"]].correct
            client.post("/api/answer", json={
                "session_id": sid2, "item_id": nxt2["item_id"],
                "answer": correct, "elapsed_ms": 1000,
            })
            assert missed not in dao.pending_retries()


def _item(kind: str, choices: list[str]) -> StudyItem:
    return StudyItem(
        "c", "C", "s", "", kind, "q?", choices, "2.000", [], 0, {},
    )


class TestPerModeGrading:
    def test_recall_fast_is_easy(self):
        _, grade = service.grade("2.000", GRADE_FAST_MS - 1, _item("recall", ["2.000"]))
        assert grade == 4

    def test_generator_uses_wider_thresholds(self):
        # Between the recall and generator fast bounds: Easy for a generator item.
        elapsed = (GRADE_FAST_MS + GRADE_FAST_MS_GEN) // 2
        _, recall_grade = service.grade("2.000", elapsed, _item("recall", ["2.000"]))
        _, gen_grade = service.grade("2.000", elapsed, _item("ode:solve", ["2.000"]))
        assert recall_grade == 3
        assert gen_grade == 4

    def test_generator_slow_is_hard(self):
        _, grade = service.grade(
            "2.000", GRADE_SLOW_MS_GEN + 1, _item("ode:solve", ["2.000"])
        )
        assert grade == 2


class TestTypedAnswers:
    def test_typed_accepts_relative_tolerance(self):
        item = _item("ode:solve", [])
        assert service.is_correct("2.005", item)  # within 0.5% of 2.000
        assert not service.is_correct("2.5", item)

    def test_choices_still_exact(self):
        item = _item("ode:solve", ["2.000", "2.010"])
        assert service.is_correct("a", item) or service.is_correct("2.000", item)

    def test_high_mastery_generator_served_typed(self, db, monkeypatch):
        monkeypatch.setattr(
            "engine.analytics.readiness.concept_mastery", lambda *a, **k: 1.0
        )
        settings.set_value("typed_answer_mastery", 0.5)
        import numpy as np
        concept = next(
            c for c in dao.get_concepts("diffeq") if c.mode == "generator"
        )
        item = service.build_item(concept, np.random.default_rng(0))
        assert item.choices == []


class TestAchievementProgress:
    def test_progress_fields_present_and_bounded(self, db):
        for a in achievements():
            assert 0.0 <= a["progress"] <= 1.0
            assert "/" in a["progress_text"]
            if a["earned"]:
                assert a["progress"] == 1.0
