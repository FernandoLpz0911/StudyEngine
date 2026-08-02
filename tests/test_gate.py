"""Study gate: quota counting, bail ration, and the exam-date lifecycle.

Everything here is the headless half of the gate — no display, no PyGObject, no
GNOME. That split is the point: the decision of whether to block the desktop is
testable, and only the window that carries it out needs a screen.
"""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import engine.subjects  # noqa: F401
from engine import api, config
from engine.cli import gate as gate_cli
from engine.db import dao
from engine.gate import keys, quota, schedule

SUBJECT = config.GATE_SUBJECT


def _answer(subject: str = SUBJECT, *, correct: bool, concept: str | None = None) -> None:
    """Log one settled answer the way the study loop would."""
    session = dao.create_session(subject)
    concept = concept or dao.get_concepts(subject)[0].id
    item = dao.log_shown(session, concept, subject, kind="test", correct_answer="1")
    dao.log_answered(item, user_answer="1", is_correct=correct, grade=3, elapsed_ms=5000)


class TestQuotaCounting:
    def test_closed_before_any_work(self, db):
        state = quota.status()
        assert state.is_open is False
        assert state.reason == "closed"
        assert state.correct == 0
        assert state.remaining == state.quota

    def test_wrong_answers_never_open_the_gate(self, db):
        for _ in range(quota.status().quota + 5):
            _answer(correct=False)
        state = quota.status()
        assert state.is_open is False
        assert state.correct == 0
        assert state.remaining == state.quota

    def test_correct_answers_pay_it_down(self, db):
        _answer(correct=True)
        _answer(correct=True)
        state = quota.status()
        assert state.correct == 2
        assert state.remaining == state.quota - 2
        assert state.is_open is False

    def test_opens_exactly_at_quota(self, db):
        target = quota.status().quota
        for _ in range(target - 1):
            _answer(correct=True)
        assert quota.status().is_open is False
        _answer(correct=True)
        state = quota.status()
        assert state.is_open is True
        assert state.reason == "paid"

    def test_other_subjects_do_not_pay_the_quota(self, db):
        other = "diffeq" if SUBJECT != "diffeq" else "proofs"
        for _ in range(quota.status().quota + 2):
            _answer(other, correct=True)
        state = quota.status()
        assert state.correct == 0
        assert state.is_open is False


class TestBails:
    def test_bail_opens_the_gate_for_the_day(self, db):
        assert quota.status().is_open is False
        state = quota.spend_bail()
        assert state.is_open is True
        assert state.reason == "bailed"
        assert quota.status().is_open is True

    def test_ration_decrements(self, db):
        ration = config.GATE_BAIL_RATION
        assert quota.bails_left() == ration
        quota.spend_bail()
        assert quota.bails_left() == ration - 1

    def test_ration_runs_out(self, db):
        for _ in range(config.GATE_BAIL_RATION):
            quota.spend_bail()
        assert quota.bails_left() == 0
        with pytest.raises(ValueError):
            quota.spend_bail()

    def test_bails_age_out_of_the_window(self, db):
        old = datetime.now() - timedelta(days=config.GATE_BAIL_WINDOW_DAYS + 1)
        dao.record_bail(today=old.date())
        with dao.get_connection() as conn:
            conn.execute("UPDATE gate_bail SET bailed_at = ?", (old.isoformat(),))
        assert quota.bails_left() == config.GATE_BAIL_RATION

    def test_yesterdays_bail_does_not_open_today(self, db):
        dao.record_bail(today=dao._local_today() - timedelta(days=1))
        assert quota.status().is_open is False


class TestExamLifecycle:
    def test_no_exam_date_means_no_suspension(self):
        now = datetime(2026, 8, 1, 9, 0)
        assert schedule.suspension_reason(None, now, 22) is None

    def test_ordinary_day_is_not_suspended(self):
        exam = date(2026, 9, 21)
        assert schedule.suspension_reason(exam, datetime(2026, 9, 10, 9, 0), 22) is None

    def test_eve_suppression_starts_at_the_hour(self):
        exam = date(2026, 9, 21)
        assert schedule.suspension_reason(exam, datetime(2026, 9, 20, 21, 59), 22) is None
        assert schedule.suspension_reason(exam, datetime(2026, 9, 20, 22, 0), 22) == "exam_eve"

    def test_exam_morning_is_suppressed(self):
        exam = date(2026, 9, 21)
        assert schedule.suspension_reason(exam, datetime(2026, 9, 21, 7, 0), 22) == "exam_eve"

    def test_retires_after_the_exam(self):
        exam = date(2026, 9, 21)
        assert schedule.suspension_reason(exam, datetime(2026, 9, 22, 9, 0), 22) == "retired"
        assert schedule.is_retired(exam, date(2026, 9, 22)) is True
        assert schedule.is_retired(exam, date(2026, 9, 21)) is False

    def test_days_until_counts_down(self):
        assert schedule.days_until(date(2026, 9, 21), date(2026, 7, 29)) == 54
        assert schedule.days_until(date(2026, 9, 21), date(2026, 9, 21)) == 0

    def test_status_reports_suspension_as_open(self, db):
        dao.set_exam_date(SUBJECT, (dao._local_today() - timedelta(days=1)).isoformat())
        state = quota.status()
        assert state.is_open is True
        assert state.reason == "retired"

    def test_status_carries_the_countdown(self, db):
        exam = dao._local_today() + timedelta(days=30)
        dao.set_exam_date(SUBJECT, exam.isoformat())
        state = quota.status()
        assert state.exam_date == exam.isoformat()
        assert state.days_left == 30


class TestKeybindingTypes:
    """The 'no binding' literal must match the GVariant type gsettings printed.

    Sending `''` to an array key is rejected, so a mis-typed empty silently
    leaves that shortcut armed behind the gate.
    """

    def test_populated_array(self):
        assert keys._empty_for("['<Super>Tab']") == "[]"

    def test_annotated_empty_array(self):
        assert keys._empty_for("@as []") == "[]"

    def test_plain_string(self):
        assert keys._empty_for("'Super_L'") == "''"

    def test_empty_string(self):
        assert keys._empty_for("''") == "''"


class TestApi:
    def test_gate_endpoint_mirrors_status(self, db):
        resp = TestClient(api.app).get("/api/gate")
        assert resp.status_code == 200
        assert resp.json() == quota.status().as_dict()

    def test_bail_endpoint_spends_one(self, db):
        client = TestClient(api.app)
        before = quota.bails_left()
        body = client.post("/api/gate/bail", json={}).json()
        assert body["is_open"] is True
        assert quota.bails_left() == before - 1

    def test_bail_endpoint_409s_when_exhausted(self, db):
        client = TestClient(api.app)
        for _ in range(config.GATE_BAIL_RATION):
            client.post("/api/gate/bail", json={})
        assert client.post("/api/gate/bail", json={}).status_code == 409


class TestWaylandDetection:
    """The gate cannot cover a Wayland session, so GDM offering one is a bypass."""

    def _conf(self, tmp_path, body, monkeypatch):
        path = tmp_path / "custom.conf"
        path.write_text(body)
        monkeypatch.setattr(gate_cli, "_GDM_CONF", path)

    def test_wayland_disabled_is_closed(self, tmp_path, monkeypatch):
        self._conf(tmp_path, "[daemon]\nWaylandEnable=false\n", monkeypatch)
        assert gate_cli.wayland_offered() is False

    def test_spacing_variations_still_count(self, tmp_path, monkeypatch):
        self._conf(tmp_path, "[daemon]\nWaylandEnable = False\n", monkeypatch)
        assert gate_cli.wayland_offered() is False

    def test_commented_out_does_not_count(self, tmp_path, monkeypatch):
        self._conf(tmp_path, "[daemon]\n#WaylandEnable=false\n", monkeypatch)
        assert gate_cli.wayland_offered() is True

    def test_absent_setting_means_offered(self, tmp_path, monkeypatch):
        self._conf(tmp_path, "[daemon]\n", monkeypatch)
        assert gate_cli.wayland_offered() is True

    def test_missing_file_is_unknown_not_a_guess(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gate_cli, "_GDM_CONF", tmp_path / "nope.conf")
        assert gate_cli.wayland_offered() is None


class TestRaisesOncePerDay:
    """The gate is one predictable interruption a day, not a 15-minute nag."""

    def test_raises_when_unpaid_and_not_yet_raised(self, db):
        assert quota.should_raise() is True

    def test_will_not_raise_twice_in_a_day(self, db):
        dao.record_raise()
        assert quota.should_raise() is False

    def test_a_killed_gate_still_counts_as_todays_raise(self, db):
        # record_raise happens before the window shows, so killing it rather than
        # paying does not bring it straight back on the next watchdog tick.
        dao.record_raise()
        assert quota.status().is_open is False  # quota still unpaid
        assert quota.should_raise() is False

    def test_yesterdays_raise_does_not_block_today(self, db):
        dao.record_raise(today=dao._local_today() - timedelta(days=1))
        assert quota.should_raise() is True

    def test_paid_quota_also_stops_a_raise(self, db):
        for _ in range(quota.status().quota):
            _answer(correct=True)
        assert quota.should_raise() is False

    def test_status_is_unaffected_by_the_raise_record(self, db):
        # A running gate polls status() to know when to release; recording its own
        # raise must not make it think the quota is paid.
        dao.record_raise()
        assert quota.status().is_open is False
        assert quota.status().reason == "closed"


class TestResetBails:
    def test_reset_restores_the_full_ration(self, db):
        quota.spend_bail()
        assert quota.bails_left() < config.GATE_BAIL_RATION
        removed = dao.reset_bails()
        assert removed == 1
        assert quota.bails_left() == config.GATE_BAIL_RATION

    def test_reset_reopens_the_gate_decision(self, db):
        quota.spend_bail()
        assert quota.status().reason == "bailed"
        dao.reset_bails()
        assert quota.status().reason == "closed"


class TestLocalDayBoundary:
    """'Today' is the learner's study day: local, DST-stable, rolling over at 3am."""

    def test_day_rolls_over_in_local_time_not_utc(self, monkeypatch):
        monkeypatch.setattr(config, "STUDY_TIMEZONE", "America/Chicago")
        # 03:30 UTC on the 30th is still 22:30 on the 29th in Chicago (CDT, UTC-5).
        assert dao.local_day("2026-07-30T03:30:00+00:00") == date(2026, 7, 29)

    def test_after_midnight_still_belongs_to_the_day_before(self, monkeypatch):
        monkeypatch.setattr(config, "STUDY_TIMEZONE", "America/Chicago")
        # 00:30 and 02:59 local are the tail of the 29th, not a new day.
        assert dao.local_day("2026-07-30T05:30:00+00:00") == date(2026, 7, 29)
        assert dao.local_day("2026-07-30T07:59:00+00:00") == date(2026, 7, 29)
        # 03:00 local is where the new day starts.
        assert dao.local_day("2026-07-30T08:00:00+00:00") == date(2026, 7, 30)

    def test_bounds_start_at_the_rollover_hour_and_track_dst(self, monkeypatch):
        monkeypatch.setattr(config, "STUDY_TIMEZONE", "America/Chicago")
        summer_start, _ = dao.local_day_bounds(date(2026, 7, 29))
        winter_start, _ = dao.local_day_bounds(date(2026, 12, 15))
        assert summer_start == "2026-07-29T08:00:00+00:00"  # 03:00 CDT (UTC-5)
        assert winter_start == "2026-12-15T09:00:00+00:00"  # 03:00 CST (UTC-6)

    def test_bounds_stay_contiguous_across_the_dst_switch(self, monkeypatch):
        """The spring-forward day is 23 hours long, so a fixed +24h would leave a
        gap: answers in it would belong to no day at all."""
        monkeypatch.setattr(config, "STUDY_TIMEZONE", "America/Chicago")
        _, end = dao.local_day_bounds(date(2026, 3, 7))  # DST begins Mar 8, 2026
        next_start, _ = dao.local_day_bounds(date(2026, 3, 8))
        assert end == next_start

    def test_study_today_and_local_day_agree(self, monkeypatch):
        """One rule, two inputs: a stored UTC instant and a local wall clock."""
        monkeypatch.setattr(config, "STUDY_TIMEZONE", "America/Chicago")
        assert dao.study_today() == dao.local_day(dao.local_now())

    def test_bounds_are_half_open_and_contiguous(self, monkeypatch):
        monkeypatch.setattr(config, "STUDY_TIMEZONE", "America/Chicago")
        _, end = dao.local_day_bounds(date(2026, 7, 29))
        next_start, _ = dao.local_day_bounds(date(2026, 7, 30))
        assert end == next_start

    def test_unknown_timezone_falls_back_to_utc(self, monkeypatch):
        monkeypatch.setattr(config, "STUDY_TIMEZONE", "Mars/Olympus_Mons")
        assert dao.local_day("2026-07-30T03:30:00+00:00") == date(2026, 7, 30)

    def test_correct_today_uses_the_local_day(self, db, monkeypatch):
        monkeypatch.setattr(config, "STUDY_TIMEZONE", "America/Chicago")
        _answer(correct=True)
        # Logged "now", so it lands on the Chicago day, not necessarily the UTC one.
        assert dao.count_correct_today(subject=SUBJECT) == 1
        assert dao.count_correct_today(
            subject=SUBJECT, today=dao._local_today() - timedelta(days=1)
        ) == 0
