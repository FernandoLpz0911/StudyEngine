"""Ascent (the number guided work moves) and Slog (the time diagnostic).

Ascent exists because one number cannot honestly say both "you have worked
through this" and "you would pass on Sunday". These tests pin the property that
makes the split safe rather than self-serving: ascent and readiness converge at
the top of the ladder, so the gap between them is exactly how much of the
learner's standing is still propped up.
"""
from __future__ import annotations

import pytest

import engine.subjects  # noqa: F401  (registers the problem generators)
from engine import config, service, teaching
from engine.analytics import ascent as ascent_mod
from engine.analytics import slog as slog_mod
from engine.analytics.ascent import concept_ascent, rung_progress, subject_ascent
from engine.db import dao
from engine.engagement import RecordTracker
from engine.teaching import PAIRED, SOLO, STUDY


class TestRungProgress:
    def test_no_evidence_is_no_progress_not_bad_progress(self):
        assert rung_progress(None, 0.8) == 0.0

    def test_progress_is_accuracy_against_the_bar(self):
        assert rung_progress(0.4, 0.8) == pytest.approx(0.5)

    def test_overshooting_the_bar_earns_no_extra_credit(self):
        """Clearing the bar promotes you; it does not bank surplus."""
        assert rung_progress(1.0, 0.8) == 1.0

    def test_a_higher_bar_means_less_progress_for_the_same_work(self):
        assert rung_progress(0.8, 0.92) < rung_progress(0.8, 0.80)


class TestConceptAscent:
    def test_the_ladder_is_ordered(self):
        assert (
            concept_ascent(STUDY, 0.0, 0.8)
            < concept_ascent(PAIRED, 0.0, 0.8)
            < concept_ascent(SOLO, 0.0, 0.8)
        )

    def test_a_fully_climbed_concept_reads_one(self):
        assert concept_ascent(SOLO, 0.9, 0.8) == 1.0

    def test_guided_work_moves_it(self):
        """The requirement Ascent exists for: a hard day of scaffolded work that
        graduates nothing still shows movement."""
        assert concept_ascent(PAIRED, 0.6, 0.8) > concept_ascent(PAIRED, 0.2, 0.8)

    def test_remediation_reads_as_lost_ground(self):
        """Ascent describes where a concept stands now, not how far it once got."""
        assert concept_ascent(STUDY, None, 0.8) < concept_ascent(SOLO, 0.2, 0.8)

    def test_it_converges_on_readiness_at_the_top(self):
        """The property that keeps the second number honest: on the top rung the
        remaining climb *is* unaided accuracy against the bar."""
        top = concept_ascent(SOLO, 0.4, 0.8)
        expected = (2 + 0.4 / 0.8) / len(ascent_mod.RUNGS)
        assert top == pytest.approx(expected)


class TestSubjectAscent:
    def test_a_fresh_subject_has_not_climbed(self, db):
        result = subject_ascent("examp")
        assert result.ascent == 0.0
        assert result.at_study == len(dao.get_concepts("examp"))

    def test_unseen_concepts_count_at_zero(self, db):
        """A progress bar that rises when work is *added* is worse than none."""
        result = subject_ascent("examp")
        assert len(result.concepts) == len(dao.get_concepts("examp"))

    def test_guided_work_raises_it_while_readiness_holds(self, db):
        """The whole point of the split, end to end."""
        import numpy as np

        from engine.analytics.projection import projected_score

        before_ascent = subject_ascent("examp").ascent
        before_score = projected_score("examp").score
        for concept in dao.get_concepts("examp")[:6]:
            for _ in range(3):
                session = dao.create_session("examp")
                item = service.build_item(
                    concept, np.random.default_rng(0), stage=teaching.PAIRED
                )
                item_id = service.log_item_shown(session, item)
                service.settle_answer(
                    item_id, item, item.correct, 20000, RecordTracker.snapshot()
                )
        assert subject_ascent("examp").ascent > before_ascent
        assert projected_score("examp").score == pytest.approx(before_score)


class TestSlog:
    def test_nothing_to_compare_against_is_silence_not_a_flag(self):
        assert not slog_mod.flagged(400.0, None)
        assert not slog_mod.flagged(None, 200.0)

    def test_far_above_the_norm_is_flagged(self):
        assert slog_mod.flagged(400.0, 200.0, multiple=1.5)

    def test_near_the_norm_is_not(self):
        assert not slog_mod.flagged(220.0, 200.0, multiple=1.5)

    def test_a_single_slow_answer_does_not_make_a_slog(self, db):
        """A median of one attempt is that attempt, and would mostly report
        interruptions."""
        concept = dao.get_concepts("examp")[0]
        session = dao.create_session("examp")
        item_id = dao.log_shown(session, concept.id, "examp", "x", stage="solo")
        dao.log_answered(item_id, "x", True, 3, 900_000)
        rows = {r.concept_id: r for r in slog_mod.subject_slogs("examp")}
        assert rows[concept.id].solve_s is None

    def test_the_two_readings_are_split_by_stage(self, db):
        concept = dao.get_concepts("examp")[0]
        session = dao.create_session("examp")
        for stage, ms in (("solo", 10_000), ("paired", 600_000)):
            for _ in range(config.SLOG_MIN_SAMPLES):
                item_id = dao.log_shown(
                    session, concept.id, "examp", "x", stage=stage
                )
                dao.log_answered(item_id, "x", True, 3, ms)
        row = next(r for r in slog_mod.subject_slogs("examp") if r.concept_id == concept.id)
        assert row.solve_s == 10
        assert row.understand_s == 600

    def test_it_feeds_nothing(self, db):
        """Diagnostic only — a slog must not touch the schedule or readiness."""
        from engine.analytics.projection import projected_score

        concept = dao.get_concepts("examp")[0]
        session = dao.create_session("examp")
        before = projected_score("examp").score
        for _ in range(config.SLOG_MIN_SAMPLES):
            item_id = dao.log_shown(session, concept.id, "examp", "x", stage="paired")
            dao.log_answered(item_id, "x", True, 3, 900_000)
        assert slog_mod.subject_slogs("examp")
        assert projected_score("examp").score == pytest.approx(before)
