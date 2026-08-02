"""Readiness as a projected exam score (ADR-0012).

The metric this replaces — a count of concepts over a mastery threshold — read
6/34 for a plan implying ~88% per-concept accuracy, and optimising it recommended
dropping ten concepts, which a projected score shows *costs* about a mark. These
tests pin the model that makes those two facts visible.
"""
from datetime import timedelta

import pytest

import engine.subjects  # noqa: F401
from engine import config
from engine.analytics.projection import p_exam, p_skill, projected_score
from engine.db import dao
from engine.scheduler import policy, store

SUBJECT = config.GATE_SUBJECT


class TestSkillModel:
    def test_never_answered_is_no_skill(self):
        assert p_skill(None, 0.9) == 0.0

    def test_skill_is_accuracy_discounted_by_forgetting(self):
        assert p_skill(0.9, 0.9) == pytest.approx(0.81)

    def test_confidence_is_not_in_the_estimate(self):
        """Mastery multiplies in rep-confidence, which measures how much evidence
        there is rather than how good the learner is. Folding it in marks a
        lightly practised concept down twice."""
        accuracy, retention = 0.9, 0.93
        thin_confidence = 2 / config.MASTERY_TARGET_REPS
        assert p_skill(accuracy, retention) > accuracy * retention * thin_confidence


class TestGuessingFloor:
    def test_total_ignorance_still_scores_one_in_five(self):
        assert p_exam(0.0) == pytest.approx(config.EXAM_GUESS_P)

    def test_certainty_is_unaffected(self):
        assert p_exam(1.0) == pytest.approx(1.0)

    def test_the_floor_lifts_but_never_lowers(self):
        assert p_exam(0.5) > 0.5

    def test_clamped_to_a_probability(self):
        assert p_exam(-1.0) == pytest.approx(config.EXAM_GUESS_P)
        assert p_exam(2.0) == pytest.approx(1.0)


class TestProjectedScore:
    def test_an_untouched_syllabus_scores_the_guessing_floor(self, db):
        p = projected_score(SUBJECT)
        assert p.score == pytest.approx(p.questions * config.EXAM_GUESS_P, abs=0.2)
        assert p.passing is False

    def test_unseen_concepts_still_contribute(self, db):
        """The exam asks about them whether or not they were studied, so dropping
        a concept costs the gap between studied and guessed — not its whole
        weight. This is what reversed the trim decision."""
        p = projected_score(SUBJECT)
        assert p.score > 0

    def test_studying_raises_the_projection(self, db):
        before = projected_score(SUBJECT).score
        session = dao.create_session(SUBJECT)
        for concept in dao.get_concepts(SUBJECT)[:10]:
            for _ in range(4):
                item = dao.log_shown(session, concept.id, SUBJECT, kind="test")
                dao.log_answered(item, "1", is_correct=True, grade=4, elapsed_ms=1000)
                store.save(store.apply_rating(store.get_or_create(concept.id), 4))
        assert projected_score(SUBJECT).score > before

    def test_reports_against_the_pass_mark_and_target(self, db):
        p = projected_score(SUBJECT)
        assert p.pass_mark == config.EXAM_PASS_MARK
        assert p.target == config.EXAM_PASS_MARK + config.EXAM_TARGET_MARGIN
        assert p.margin == pytest.approx(p.score - p.pass_mark, abs=0.05)

    def test_weakest_concepts_are_surfaced_lowest_first(self, db):
        weakest = projected_score(SUBJECT).weakest
        assert weakest == sorted(weakest, key=lambda row: row[1])


class TestDrillsTargetMarks:
    def _seen(self, concept_id, correct, n=4):
        session = dao.create_session(SUBJECT)
        for _ in range(n):
            item = dao.log_shown(session, concept_id, SUBJECT, kind="test")
            dao.log_answered(
                item, "1", is_correct=correct, grade=4 if correct else 1,
                elapsed_ms=1000,
            )
            store.save(
                store.apply_rating(store.get_or_create(concept_id), 4 if correct else 1)
            )

    def test_a_heavy_mid_concept_outranks_a_light_weak_one(self, db, monkeypatch):
        """Lowest mastery alone ignores what a concept is worth: three marks at
        0.70 beat one mark at 0.50."""
        concepts = dao.get_concepts(SUBJECT)
        heavy = next(c for c in concepts if c.exam_weight == 3)
        light = next(c for c in concepts if c.exam_weight == 1)
        self._seen(heavy.id, correct=True)
        self._seen(light.id, correct=False)

        scores = {heavy.id: 0.70, light.id: 0.50}
        monkeypatch.setattr(
            "engine.analytics.projection.concept_p_exam",
            lambda cid, now=None: scores.get(cid, 0.99),
        )
        selection = policy.select_drill(SUBJECT)
        assert selection is not None
        assert selection.concept.id == heavy.id

    def test_rotation_still_beats_value(self, db):
        """Everything gets one drill before anything gets two, so a long top-up
        spaces rather than masses — value only breaks ties within a round."""
        concepts = dao.get_concepts(SUBJECT)[:3]
        for c in concepts:
            self._seen(c.id, correct=False)
        session = dao.create_session(SUBJECT)
        picked = []
        for _ in range(3):
            selection = policy.select_drill(SUBJECT)
            picked.append(selection.concept.id)
            dao.log_shown(
                session, selection.concept.id, SUBJECT, kind="test", reason="drill"
            )
        assert len(set(picked)) == 3


class TestGateCarriesTheProjection:
    def test_status_reports_the_projection_not_a_mastered_count(self, db):
        from engine.gate import quota

        dao.set_setting(
            f"exam_date.{SUBJECT}",
            (dao.local_now().date() + timedelta(days=40)).isoformat(),
        )
        state = quota.status().as_dict()
        assert "projected_score" in state
        assert "concepts_mastered" not in state, "the misleading metric is gone"
        assert state["pass_mark"] == config.EXAM_PASS_MARK
        assert state["questions_total"] == config.EXAM_QUESTIONS
