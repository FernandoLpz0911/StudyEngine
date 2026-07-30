"""Exam pacing: coverage deadline, intro quota, frontier order, drills, taper.

The pacing rules exist because three things went wrong at once (ADR-0007,
ADR-0008, ADR-0009): reviews starved the frontier so coverage froze, a
high-accuracy day ran out of quota-payable items and stranded the learner behind
their own gate, and FSRS scheduled reviews for after the exam. Each is pinned
here, mostly through the pure functions so no clock or display is involved.
"""
from datetime import date, timedelta

import engine.subjects  # noqa: F401
from engine import config, service
from engine.analytics import pace
from engine.db import dao
from engine.db.dao import Concept
from engine.scheduler import policy, store

SUBJECT = config.GATE_SUBJECT


def _concept(cid: str, prereqs: list[str], weight: int = 1) -> Concept:
    return Concept(
        id=cid, subject="t", name=cid, category=None, mode="generator",
        exam_weight=weight, prerequisites=prereqs,
    )


class TestCoverageDeadline:
    def test_deadline_is_the_exam_minus_consolidation(self):
        assert pace.coverage_deadline(date(2026, 9, 21), 40) == date(2026, 8, 12)

    def test_no_exam_date_means_no_deadline(self):
        assert pace.coverage_deadline(None) is None

    def test_deadline_moves_with_the_exam(self):
        moved = pace.coverage_deadline(date(2026, 10, 1), 40)
        assert moved == date(2026, 8, 22)


class TestIntroQuota:
    def test_backlog_is_spread_over_the_days_remaining(self):
        assert pace.intro_quota(28, 14, cap=8) == 2

    def test_a_missed_day_raises_tomorrows_share(self):
        # Same backlog, one fewer day: the divisor shrinks, so the quota rises
        # without anyone having recorded a debt.
        assert pace.intro_quota(28, 7, cap=8) == 4

    def test_rounds_up_so_a_remainder_is_never_dropped(self):
        assert pace.intro_quota(29, 14, cap=8) == 3

    def test_bounded_by_the_new_per_day_cap(self):
        assert pace.intro_quota(80, 2, cap=8) == 8

    def test_zero_once_coverage_is_complete(self):
        assert pace.intro_quota(0, 14, cap=8) == 0

    def test_past_the_deadline_introduces_as_fast_as_the_cap_allows(self):
        assert pace.intro_quota(10, -3, cap=8) == 8

    def test_no_deadline_owes_nothing(self):
        assert pace.intro_quota(28, None, cap=8) == 0


class TestFrontierOrder:
    def test_reach_counts_transitive_dependents(self):
        concepts = [
            _concept("gateway", []),
            _concept("mid", ["gateway"]),
            _concept("leaf", ["mid"]),
            _concept("dead_end", []),
        ]
        reach = policy.downstream_reach(concepts)
        assert reach["gateway"] == 2  # mid and leaf both sit behind it
        assert reach["mid"] == 1
        assert reach["leaf"] == 0
        assert reach["dead_end"] == 0

    def test_a_gateway_outranks_a_heavier_dead_end(self):
        concepts = [
            _concept("gateway", [], weight=1),
            _concept("behind", ["gateway"], weight=3),
            _concept("dead_end", [], weight=3),
        ]
        reach = policy.downstream_reach(concepts)
        ranked = max(
            [concepts[0], concepts[2]],
            key=lambda c: policy._frontier_key(c, reach),
        )
        assert ranked.id == "gateway"

    def test_exam_weight_breaks_ties_between_equal_reach(self):
        concepts = [_concept("light", [], weight=1), _concept("heavy", [], weight=3)]
        reach = policy.downstream_reach(concepts)
        ranked = max(concepts, key=lambda c: policy._frontier_key(c, reach))
        assert ranked.id == "heavy"

    def test_a_prerequisite_cycle_does_not_recurse_forever(self):
        # A malformed graph must not hang selection, and must not let a concept
        # inflate its own rank by reaching itself round the loop.
        concepts = [_concept("a", ["b"]), _concept("b", ["a"])]
        assert policy.downstream_reach(concepts) == {"a": 1, "b": 1}


class TestExamTaper:
    def test_far_from_the_exam_the_normal_target_holds(self):
        assert store.desired_retention(60) == config.TARGET_RETENTION
        assert store.desired_retention(None) == config.TARGET_RETENTION

    def test_target_climbs_as_the_exam_approaches(self):
        far = store.desired_retention(config.EXAM_TAPER_DAYS - 1)
        near = store.desired_retention(3)
        assert config.TARGET_RETENTION < far < near <= config.EXAM_PEAK_RETENTION

    def test_peaks_on_exam_day(self):
        assert store.desired_retention(0) == config.EXAM_PEAK_RETENTION

    def test_review_is_never_scheduled_past_the_exam(self, db):
        exam = dao.local_now().date() + timedelta(days=3)
        dao.set_setting(f"exam_date.{SUBJECT}", exam.isoformat())
        concept = dao.get_concepts(SUBJECT)[0].id
        state = store.get_or_create(concept)
        for _ in range(8):  # push the interval well past three days
            state = store.apply_rating(state, 4, subject=SUBJECT)
            store.save(state)
        assert state.due is not None
        assert state.due.date() <= exam


class TestDrills:
    def test_drills_rotate_instead_of_massing_one_concept(self, db):
        """A correct drill leaves card state alone, so mastery cannot break the
        tie a second time — without rotation the same concept is served all day."""
        concepts = dao.get_concepts(SUBJECT)[:4]
        for concept in concepts:  # make them all seen, so all are drillable
            store.save(store.apply_rating(store.get_or_create(concept.id), 3))

        picked = []
        session = dao.create_session(SUBJECT)
        for _ in range(4):
            selection = policy.select_drill(SUBJECT)
            assert selection is not None
            picked.append(selection.concept.id)
            dao.log_shown(
                session, selection.concept.id, SUBJECT, kind="test", reason="drill"
            )
        assert len(set(picked)) == 4

    def test_unseen_concepts_are_never_drilled(self, db):
        # Nothing has been introduced yet, so there is nothing to practise.
        assert policy.select_drill(SUBJECT) is None

    def test_correct_drill_leaves_the_schedule_untouched(self, db):
        concept = dao.get_concepts(SUBJECT)[0]
        store.save(store.apply_rating(store.get_or_create(concept.id), 3))
        before = store.get_or_create(concept.id)

        item = service.StudyItem(
            concept_id=concept.id, concept_name=concept.name, subject=SUBJECT,
            reason="drill", kind="test", question="q", choices=[], correct="1",
            explain=[], seed=0, params={},
        )
        service._apply_schedule(item, correct=True, grade=4)

        after = store.get_or_create(concept.id)
        assert (after.reps, after.due, after.stability) == (
            before.reps, before.due, before.stability
        )

    def test_missed_drill_reschedules_without_advancing_reps(self, db):
        concept = dao.get_concepts(SUBJECT)[0]
        for _ in range(3):  # reach the review state, where a miss is a lapse
            store.save(store.apply_rating(store.get_or_create(concept.id), 3))
        before = store.get_or_create(concept.id)

        item = service.StudyItem(
            concept_id=concept.id, concept_name=concept.name, subject=SUBJECT,
            reason="drill", kind="test", question="q", choices=[], correct="1",
            explain=[], seed=0, params={},
        )
        service._apply_schedule(item, correct=False, grade=1)

        after = store.get_or_create(concept.id)
        assert after.reps == before.reps, "a failed drill must not raise rep-confidence"
        assert after.due < before.due, "forgetting should pull the review forward"

    def test_drills_stay_out_of_the_fsrs_weight_fit(self, db):
        concept = dao.get_concepts(SUBJECT)[0].id
        session = dao.create_session(SUBJECT)
        scheduled = dao.log_shown(session, concept, SUBJECT, kind="test")
        drilled = dao.log_shown(
            session, concept, SUBJECT, kind="test", reason="drill"
        )
        dao.log_answered(scheduled, "1", is_correct=True, grade=3, elapsed_ms=1000)
        dao.log_answered(drilled, "1", is_correct=True, grade=3, elapsed_ms=1000)

        assert len(dao.graded_reviews()) == 1


class TestIntroductionIsNotStarved:
    def _fully_reviewed(self, subject: str) -> None:
        """Answer every available concept once, so the review queue is non-empty."""
        for concept in dao.get_concepts(subject)[:6]:
            store.save(store.apply_rating(store.get_or_create(concept.id), 3))

    def test_owed_introductions_outrank_due_reviews(self, db):
        exam = dao.local_now().date() + timedelta(days=54)
        dao.set_setting(f"exam_date.{SUBJECT}", exam.isoformat())
        self._fully_reviewed(SUBJECT)

        assert pace.intro_owed(SUBJECT) > 0
        selection = policy.select_next(SUBJECT)
        assert selection is not None
        assert selection.reason == "new", "reviews must not starve the coverage deadline"

    def test_a_paced_subject_stops_at_the_days_share(self, db):
        exam = dao.local_now().date() + timedelta(days=54)
        dao.set_setting(f"exam_date.{SUBJECT}", exam.isoformat())
        session = dao.create_session(SUBJECT)

        introduced = 0
        while pace.intro_owed(SUBJECT) > 0:
            selection = policy.select_next(SUBJECT)
            assert selection is not None and selection.reason == "new"
            item = dao.log_shown(
                session, selection.concept.id, SUBJECT, kind="test", reason="new"
            )
            dao.log_answered(item, "1", is_correct=True, grade=3, elapsed_ms=1000)
            store.save(store.apply_rating(store.get_or_create(selection.concept.id), 3))
            introduced += 1
            assert introduced < 20, "the day's share must be finite"

        # The deadline is a ceiling too: with today's share paid and nothing due,
        # a paced subject does not race ahead into the new-per-day cap.
        after = policy.select_next(SUBJECT)
        assert after is None or after.reason != "new"

    def test_a_subject_without_an_exam_keeps_the_old_frontier(self, db):
        other = "diffeq"
        assert dao.get_exam_date(other) is None
        selection = policy.select_next(other)
        assert selection is not None
        assert selection.reason == "new"


class TestPaceReadout:
    def test_reports_coverage_against_the_deadline(self, db):
        exam = dao.local_now().date() + timedelta(days=54)
        dao.set_setting(f"exam_date.{SUBJECT}", exam.isoformat())

        report = pace.subject_pace(SUBJECT)
        assert report.total == len(dao.get_concepts(SUBJECT))
        assert report.seen == 0
        assert report.unseen == report.total
        assert report.coverage_deadline == (exam - timedelta(days=40)).isoformat()
        assert report.intro_owed_today > 0

    def test_behind_when_the_cap_can_no_longer_clear_the_backlog(self, db):
        # One day left to introduce everything, at most new_per_day of them.
        exam = dao.local_now().date() + timedelta(days=41)
        dao.set_setting(f"exam_date.{SUBJECT}", exam.isoformat())
        assert pace.subject_pace(SUBJECT).coverage_on_track is False

    def test_on_track_with_room_to_spare(self, db):
        exam = dao.local_now().date() + timedelta(days=140)
        dao.set_setting(f"exam_date.{SUBJECT}", exam.isoformat())
        assert pace.subject_pace(SUBJECT).coverage_on_track is True
