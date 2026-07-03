"""Exam dates: storage, countdown/pace in readiness, API endpoint."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import engine.subjects  # noqa: F401
from engine import api
from engine.analytics.readiness import subject_readiness
from engine.db import dao


def _client():
    return TestClient(api.app)


class TestStorage:
    def test_unset_is_none(self, db):
        assert dao.get_exam_date("diffeq") is None

    def test_set_get_clear(self, db):
        dao.set_exam_date("diffeq", "2026-08-01")
        assert dao.get_exam_date("diffeq") == date(2026, 8, 1)
        dao.set_exam_date("diffeq", None)
        assert dao.get_exam_date("diffeq") is None

    def test_bad_date_rejected(self, db):
        with pytest.raises(ValueError):
            dao.set_exam_date("diffeq", "next tuesday")


class TestCountdown:
    def test_no_date_gives_nulls(self, db):
        r = subject_readiness("diffeq")
        assert r["exam_date"] is None
        assert r["days_left"] is None
        assert r["pace_new_per_day"] is None

    def test_days_left_and_pace(self, db):
        exam = dao._local_today() + timedelta(days=10)
        dao.set_exam_date("diffeq", exam.isoformat())
        r = subject_readiness("diffeq")
        assert r["days_left"] == 10
        # Fresh database: all concepts unseen, so pace = unseen / days.
        assert r["pace_new_per_day"] == round(r["n_concepts"] / 10, 1)

    def test_past_exam_has_no_pace(self, db):
        dao.set_exam_date("diffeq", (dao._local_today() - timedelta(days=1)).isoformat())
        r = subject_readiness("diffeq")
        assert r["days_left"] == -1
        assert r["pace_new_per_day"] is None


class TestEndpoint:
    def test_set_and_surface_in_progress(self, db):
        exam = (dao._local_today() + timedelta(days=30)).isoformat()
        with _client() as client:
            res = client.post(
                "/api/exam_date", json={"subject": "diffeq", "date": exam}
            )
            assert res.status_code == 200
            subj = client.get("/api/progress/diffeq").json()
            assert subj["exam_date"] == exam
            assert subj["days_left"] == 30

    def test_unknown_subject_422(self, db):
        with _client() as client:
            res = client.post(
                "/api/exam_date", json={"subject": "underwater-basketweaving"}
            )
            assert res.status_code == 422

    def test_bad_date_422(self, db):
        with _client() as client:
            res = client.post(
                "/api/exam_date", json={"subject": "diffeq", "date": "not-a-date"}
            )
            assert res.status_code == 422
