"""The teaching ladder: which stage a concept is owed, and what a stage measures.

These are the rules that decide whether an item teaches or tests, so they are
tested as pure functions over an attempt history rather than through the loop.
"""
from __future__ import annotations

import pytest

import engine.subjects  # noqa: F401  (registers the problem generators)
from engine import config, service, teaching
from engine.db import dao
from engine.teaching import PAIRED, SOLO, STUDY, Attempt


def attempts(*spec: tuple[str, bool]) -> list[Attempt]:
    """Build a newest-first history from (stage, correct) pairs."""
    return [Attempt(stage, correct) for stage, correct in spec]


def idk(*spec: tuple[str, bool]) -> list[Attempt]:
    """Same, but the most recent attempt is a declared don't-know."""
    rows = attempts(*spec)
    return [Attempt(rows[0].stage, False, True), *rows[1:]]


class TestRequiredAccuracy:
    def test_leaf_concept_sits_at_the_floor(self):
        assert teaching.required_accuracy(0) == pytest.approx(config.ACCURACY_FLOOR)

    def test_a_gateway_is_held_to_more_than_a_leaf(self):
        assert teaching.required_accuracy(4) > teaching.required_accuracy(0)

    def test_the_ramp_saturates(self):
        """Past the saturation point the bar stops climbing, so no concept is
        held to an accuracy no honest measurement reaches."""
        wide = teaching.required_accuracy(4)
        assert teaching.required_accuracy(40) == pytest.approx(wide)
        assert wide <= 0.99

    def test_reach_scales_between_the_two(self):
        floor = teaching.required_accuracy(0)
        full = teaching.required_accuracy(4)
        mid = teaching.required_accuracy(2)
        assert floor < mid < full


class TestStageProgression:
    def test_first_contact_is_taught_not_tested(self):
        """A cold test on a never-seen concept is a near-certain miss that
        teaches nothing and costs a quota answer."""
        assert teaching.stage_for(0, None, [], 0.8) == STUDY

    def test_a_passed_study_trial_moves_up_to_paired(self):
        assert teaching.stage_for(1, 0.5, attempts((STUDY, True)), 0.8) == PAIRED

    def test_a_failed_study_trial_repeats(self):
        assert teaching.stage_for(1, 0.5, attempts((STUDY, False)), 0.8) == STUDY

    def test_repeated_study_trials_terminate(self):
        """Re-reading a solution you cannot reproduce is right, but unbounded it
        is a dead end that never returns the concept to testing."""
        history = attempts(*[(STUDY, False)] * config.MAX_CONSECUTIVE_STUDY)
        assert teaching.stage_for(1, 0.5, history, 0.8) == PAIRED

    def test_paired_accuracy_at_the_bar_takes_the_scaffold_off(self):
        history = attempts((PAIRED, True), (PAIRED, True))
        assert teaching.stage_for(4, 5.0, history, 0.8, paired_acc=1.0) == SOLO

    def test_paired_accuracy_under_the_bar_keeps_it_on(self):
        history = attempts((PAIRED, True), (PAIRED, False))
        assert teaching.stage_for(4, 5.0, history, 0.8, paired_acc=0.5) == PAIRED

    def test_graduation_consults_the_concepts_own_bar(self):
        """The defect this replaced: a fixed streak released a gateway on
        exactly the evidence that released a leaf."""
        history = attempts((PAIRED, True), (PAIRED, True), (PAIRED, True))
        assert teaching.stage_for(6, 5.0, history, 0.80, paired_acc=0.85) == SOLO
        assert teaching.stage_for(6, 5.0, history, 0.92, paired_acc=0.85) == PAIRED

    def test_solo_accuracy_below_the_bar_puts_the_scaffold_back(self):
        history = attempts((SOLO, True), (SOLO, False), (SOLO, False), (SOLO, True))
        assert teaching.stage_for(4, 5.0, history, 0.8) == PAIRED

    def test_solo_accuracy_above_the_bar_stays_solo(self):
        history = attempts(*[(SOLO, True)] * 5)
        assert teaching.stage_for(5, 5.0, history, 0.8) == SOLO

    def test_a_raised_bar_can_demote_a_concept_another_would_keep(self):
        """The same evidence, judged against a gateway's standard instead of a
        leaf's — which is the whole point of the prerequisite weighting."""
        history = attempts(*([(SOLO, True)] * 5 + [(SOLO, False)]))
        assert teaching.stage_for(6, 5.0, history, 0.80) == SOLO
        assert teaching.stage_for(6, 5.0, history, 0.92) == PAIRED


class TestStuck:
    def test_a_run_of_misses_triggers_remediation(self):
        history = attempts(*[(SOLO, False)] * config.STUCK_MISSES)
        assert teaching.is_stuck(3, 5.0, history, 0.8)

    def test_study_trials_do_not_count_toward_the_run(self):
        """Or remediation would re-trigger on its own failures forever."""
        history = attempts(
            (STUDY, False), (STUDY, False), (STUDY, False), (SOLO, True)
        )
        assert not teaching.is_stuck(3, 5.0, history, 0.8)

    def test_many_reps_with_flat_stability_is_the_treadmill(self):
        """The case this exists for: 18 reps that left stability at 0.0 — every
        answer a coin flip, every interval crashed, nothing retained."""
        history = attempts((SOLO, True), (SOLO, False), (SOLO, True), (SOLO, False))
        assert teaching.is_stuck(18, 0.0, history, 0.8)

    def test_a_growing_interval_is_not_stuck(self):
        history = attempts((SOLO, True), (SOLO, False), (SOLO, True), (SOLO, False))
        assert not teaching.is_stuck(18, 30.0, history, 0.8)

    def test_few_reps_with_low_stability_is_just_new(self):
        history = attempts((SOLO, True), (SOLO, False))
        assert not teaching.is_stuck(2, 0.0, history, 0.8)

    def test_stuck_routes_to_a_study_trial(self):
        history = attempts(*[(SOLO, False)] * config.STUCK_MISSES)
        assert teaching.stage_for(18, 0.0, history, 0.8) == STUDY


class TestMeasurement:
    def test_only_solo_attempts_are_measured(self):
        """Scaffolded answers must not reach accuracy: a projected exam score
        built from them would measure the ability to copy a solution."""
        history = attempts((PAIRED, True), (STUDY, True), (SOLO, False))
        assert teaching.solo_accuracy(history) == 0.0

    def test_no_solo_attempts_reads_as_unknown_not_zero(self):
        assert teaching.solo_accuracy(attempts((STUDY, True), (PAIRED, True))) is None

    def test_study_trials_are_not_scheduled(self):
        assert STUDY not in teaching.SCHEDULED_STAGES
        assert PAIRED in teaching.SCHEDULED_STAGES
        assert SOLO in teaching.SCHEDULED_STAGES


class TestStagedItems:
    @staticmethod
    def _generator_concept():
        return next(c for c in dao.get_concepts("diffeq") if c.mode == "generator")

    def test_study_items_carry_their_own_solution(self, db):
        import numpy as np
        item = service.build_item(
            self._generator_concept(), np.random.default_rng(0), stage=STUDY
        )
        assert item.example == item.explain
        assert not item.example_statement

    def test_paired_items_work_a_different_instance(self, db):
        """A sibling problem, not this one: an example whose answer is also the
        answer being asked for teaches copying, not the method."""
        import numpy as np
        item = service.build_item(
            self._generator_concept(), np.random.default_rng(0), stage=PAIRED
        )
        assert item.example
        assert item.example_statement
        assert item.example_statement != item.question

    def test_solo_items_are_bare(self, db):
        import numpy as np
        item = service.build_item(
            self._generator_concept(), np.random.default_rng(0), stage=SOLO
        )
        assert item.example == []
        assert item.example_statement == ""

    def test_the_stage_is_logged_with_the_answer(self, db):
        """Every accuracy read filters on it, so it has to survive the write."""
        import numpy as np
        concept = self._generator_concept()
        session_id = dao.create_session("diffeq")
        item = service.build_item(
            concept, np.random.default_rng(0), stage=STUDY
        )
        item_id = service.log_item_shown(session_id, item)
        dao.log_answered(item_id, "a", True, 3, 1000)
        assert dao.recent_attempts(concept.id, 5) == [(STUDY, True, False)]
        assert dao.get_concept_accuracy(concept.id) is None  # never solo


class TestDontKnow:
    """Declining to guess is a miss, but a more informative one (ADR-0014)."""

    def test_a_dont_know_demotes_on_its_own(self):
        """One plain statement beats waiting three items to infer the same thing."""
        assert teaching.is_stuck(3, 5.0, idk((SOLO, False)), 0.8)
        assert teaching.stage_for(3, 5.0, idk((SOLO, False)), 0.8) == STUDY

    def test_a_single_wrong_answer_does_not(self):
        """A wrong answer is ambiguous between a slip and ignorance, so it needs
        corroboration; a don't-know does not."""
        assert not teaching.is_stuck(3, 5.0, attempts((SOLO, False)), 0.8)

    def test_an_older_dont_know_does_not_pin_the_concept(self):
        """Otherwise one honest admission would hold a concept in remediation for
        as long as the window remembers it."""
        history = [*attempts((SOLO, True)), Attempt(SOLO, False, True)]
        assert not teaching.is_stuck(3, 5.0, history, 0.8)

    def test_the_sentinel_never_grades_correct(self, db):
        import numpy as np
        concept = next(c for c in dao.get_concepts("diffeq") if c.mode == "generator")
        item = service.build_item(concept, np.random.default_rng(0), stage=SOLO)
        assert not service.is_correct(service.DONT_KNOW, item)
        assert service.is_dont_know(service.DONT_KNOW)
