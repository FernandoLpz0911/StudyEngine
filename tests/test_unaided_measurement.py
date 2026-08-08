"""Every factor of readiness reads unaided evidence, and only unaided evidence.

The failure this guards against is specific and was live: `accuracy` was filtered
to solo attempts while `retention` was not, so eighteen concepts' worth of guided
answers walked the projected score up 1.4 marks with nothing unaided shown. These
tests pin all three factors — accuracy, retention, rep-confidence — plus the
guessing correction underneath them (ADR-0014).
"""
from __future__ import annotations

import pytest

import engine.subjects  # noqa: F401  (registers the problem generators)
from engine import config, service, teaching
from engine.analytics import projection, readiness
from engine.db import dao
from engine.engagement import RecordTracker
from engine.scheduler import store


def _answer(concept, stage: str, correct: bool, choices_n: int = 0) -> int:
    """Log and settle one answer at `stage`, through the real settle path."""
    import numpy as np

    session = dao.create_session(concept.subject)
    item = service.build_item(concept, np.random.default_rng(0), stage=stage)
    item.choices_n = choices_n
    item_id = service.log_item_shown(session, item)
    answer = item.correct if correct else "definitely-wrong"
    service.settle_answer(item_id, item, answer, 20000, RecordTracker.snapshot())
    return item_id


@pytest.fixture
def concept(db):
    return next(c for c in dao.get_concepts("examp") if c.mode == "generator")


class TestDeguessing:
    def test_free_response_is_left_alone(self):
        rows = [{"is_correct": 1, "choices_n": 0}] * 4
        assert dao.deguess(rows) == pytest.approx(1.0)

    def test_multiple_choice_rate_is_corrected_downward(self):
        """40% observed over four options is ~20% real — the number that changed
        the whole reading of the Exam P log."""
        rows = [{"is_correct": c, "choices_n": 4} for c in (1, 1, 0, 0, 0)]
        assert dao.deguess(rows) == pytest.approx((0.4 - 0.25) / 0.75)

    def test_chance_level_reads_as_no_skill(self):
        rows = [{"is_correct": c, "choices_n": 4} for c in (1, 0, 0, 0)]
        assert dao.deguess(rows) == pytest.approx(0.0)

    def test_the_correction_retires_as_free_response_replaces_it(self):
        """Self-retiring by construction — no flag day, no second number."""
        mixed = [{"is_correct": 1, "choices_n": 4}, {"is_correct": 1, "choices_n": 0}]
        allfree = [{"is_correct": 1, "choices_n": 0}] * 2
        assert dao.deguess(mixed) <= dao.deguess(allfree)

    def test_no_evidence_reads_as_unknown(self):
        assert dao.deguess([]) is None


class TestUnaidedMastery:
    def test_guided_answers_never_move_measured_accuracy(self, concept):
        for _ in range(4):
            _answer(concept, teaching.PAIRED, correct=True)
        assert dao.get_concept_accuracy(concept.id) is None

    def test_guided_answers_never_move_rep_confidence(self, concept):
        for _ in range(6):
            _answer(concept, teaching.PAIRED, correct=True)
        assert store.get_or_create(concept.id).reps == 6  # FSRS still advanced
        assert dao.solo_reps(concept.id) == 0             # but nothing was measured

    def test_guided_answers_never_move_retention(self, concept):
        """The hole that let scaffolding into the headline: FSRS resets its decay
        clock on any review, so readiness must decay from the last *solo* one."""
        _answer(concept, teaching.SOLO, correct=True)
        before = projection.concept_p_exam(concept.id)
        for _ in range(6):
            _answer(concept, teaching.PAIRED, correct=True)
        assert projection.concept_p_exam(concept.id) == pytest.approx(before, abs=1e-3)

    def test_a_never_unaided_concept_scores_the_guessing_floor(self, concept):
        for _ in range(6):
            _answer(concept, teaching.PAIRED, correct=True)
        assert projection.concept_p_exam(concept.id) == pytest.approx(
            config.EXAM_GUESS_P
        )
        assert readiness.concept_mastery(concept.id) == 0.0

    def test_a_guided_run_cannot_move_the_projected_score(self, db):
        """The regression test for the +1.4 marks."""
        before = projection.projected_score("examp").score
        for c in dao.get_concepts("examp")[:10]:
            for _ in range(4):
                _answer(c, teaching.PAIRED, correct=True)
        assert projection.projected_score("examp").score == pytest.approx(before)

    def test_unaided_answers_do_move_it(self, concept):
        before = projection.concept_p_exam(concept.id)
        for _ in range(4):
            _answer(concept, teaching.SOLO, correct=True)
        assert projection.concept_p_exam(concept.id) > before

    def test_a_guided_concept_can_never_be_rested(self, concept):
        """You cannot stop reviewing something you have only ever done with help."""
        from engine.scheduler.availability import is_rested

        for _ in range(12):
            _answer(concept, teaching.PAIRED, correct=True)
        mastery = readiness.concept_mastery(concept.id)
        assert not is_rested(
            mastery, store.get_or_create(concept.id).reps, 60,
            config.REST_MASTERY, config.MASTERY_TARGET_REPS, config.REST_STOP_DAYS,
        )


class TestRecordsAreUnaided:
    def test_a_study_trial_cannot_set_the_fastest_record(self, concept):
        """With the answer on screen a study trial is answerable in two seconds,
        which would take the fastest-answer record permanently."""
        _answer(concept, teaching.SOLO, correct=True)  # a slow baseline
        import numpy as np

        session = dao.create_session(concept.subject)
        item = service.build_item(concept, np.random.default_rng(0), stage="study")
        item_id = service.log_item_shown(session, item)
        res = service.settle_answer(
            item_id, item, item.correct, 200, RecordTracker.snapshot()
        )
        assert res.records == []


class TestAidedAnswers:
    """Opening the explanation on a bare item is declared, and it costs.

    The habit it exists to break: reaching for the theory mid-problem makes the
    problem easier than the exam will be, and the log had no way to know — the
    answer went in as unaided evidence (ADR-0014).
    """

    @staticmethod
    def _settle(concept, correct: bool, aided: bool, stage: str = teaching.SOLO):
        import numpy as np

        session = dao.create_session(concept.subject)
        item = service.build_item(concept, np.random.default_rng(0), stage=stage)
        item_id = service.log_item_shown(session, item)
        answer = item.correct if correct else "definitely-wrong"
        res = service.settle_answer(
            item_id, item, answer, 20000, RecordTracker.snapshot(), aided=aided
        )
        return item_id, res

    def test_an_aided_answer_is_not_measured(self, concept):
        for _ in range(4):
            self._settle(concept, correct=True, aided=True)
        assert dao.get_concept_accuracy(concept.id) is None
        assert dao.solo_reps(concept.id) == 0
        assert dao.last_solo_review(concept.id) is None

    def test_an_unaided_answer_still_is(self, concept):
        self._settle(concept, correct=True, aided=False)
        assert dao.get_concept_accuracy(concept.id) == 1.0
        assert dao.solo_reps(concept.id) == 1

    def test_aided_answers_cannot_move_the_projected_score(self, concept):
        before = projection.concept_p_exam(concept.id)
        for _ in range(6):
            self._settle(concept, correct=True, aided=True)
        assert projection.concept_p_exam(concept.id) == pytest.approx(before)

    def test_the_flag_is_logged(self, concept):
        item_id, _ = self._settle(concept, correct=True, aided=True)
        with __import__("engine.db.connection", fromlist=["x"]).get_connection() as c:
            row = c.execute(
                "SELECT aided FROM interaction WHERE id = ?", (item_id,)
            ).fetchone()
        assert row["aided"] == 1

    def test_it_reads_as_a_guided_attempt_not_a_bare_one(self, concept):
        """So the promotion and demotion rules cannot mistake it for evidence."""
        self._settle(concept, correct=True, aided=True)
        stages = [stage for stage, _, _ in dao.recent_attempts(concept.id, 5)]
        assert stages == [teaching.PAIRED]

    def test_an_aided_answer_carries_no_timing_signal(self, concept):
        """With the explanation on screen the clock cannot tell reading from
        solving, so a slow aided answer must not grade Hard."""
        import numpy as np

        item = service.build_item(
            concept, np.random.default_rng(0), stage=teaching.SOLO
        )
        _, slow = service.grade(item.correct, 10 * 60 * 1000, item, aided=True)
        _, slow_unaided = service.grade(item.correct, 10 * 60 * 1000, item)
        assert slow == 3          # Good — correctness only
        assert slow_unaided == 2  # Hard — the honest unaided reading

    def test_it_sets_no_records(self, concept):
        self._settle(concept, correct=True, aided=False)  # a slow-ish baseline
        _, res = self._settle(concept, correct=True, aided=True)
        assert res.records == []

    def test_it_forfeits_xp_and_breaks_the_combo(self, db):
        """The felt half of the cost — streak and XP stand for unaided work."""
        from engine.loop import StudyLoop

        loop = StudyLoop.start("examp", n=None)
        turn = loop.next()
        loop.settle(turn.item_id, turn.item.correct, 5000)
        earned = loop.xp
        assert loop.streak == 1

        turn2 = loop.next()
        out = loop.settle(turn2.item_id, turn2.item.correct, 5000, aided=True)
        assert out.correct is True     # the answer was right
        assert out.aided is True
        assert out.xp == 0             # and bought nothing
        assert loop.xp == earned
        assert loop.streak == 0        # combo broken

    def test_a_rebuilt_session_folds_aided_the_same_way(self, db):
        """`rebuild` replays from the log, so `aided` has to survive the round
        trip or a restarted session reports a streak the live one never had
        (ADR-0002)."""
        from engine.loop import StudyLoop

        loop = StudyLoop.start("examp", n=None)
        for aided in (False, True, False):
            turn = loop.next()
            loop.settle(turn.item_id, turn.item.correct, 5000, aided=aided)
        live = (loop.streak, loop.best, loop.xp)

        rebuilt = StudyLoop.rebuild(loop.db_id)
        assert (rebuilt.streak, rebuilt.best, rebuilt.xp) == live
