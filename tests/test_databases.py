"""FD engine correctness + answer keys for the CS 480 normalization generators."""
import engine.subjects  # noqa: F401  (registers generators)
from engine.generation.base import generate
from engine.subjects.databases import fd

SEEDS = range(60)
ALL = frozenset("ABCD")
KINDS = [
    ("fd_closure", "closure_size"),
    ("candidate_keys", "count"),
    ("bcnf_check", "violation_count"),
    ("prime_attributes", "count"),
    ("superkey_count", "count"),
]


def _parse(params):
    return [(frozenset(lhs), frozenset(rhs)) for lhs, rhs in params["fds"]]


class TestFdEngine:
    fds = [(frozenset("A"), frozenset("B")), (frozenset("B"), frozenset("C"))]

    def test_closure(self):
        assert fd.closure(frozenset("A"), self.fds) == frozenset("ABC")
        assert fd.closure(frozenset("AD"), self.fds) == ALL

    def test_is_superkey(self):
        assert fd.is_superkey(frozenset("AD"), ALL, self.fds)
        assert not fd.is_superkey(frozenset("A"), ALL, self.fds)

    def test_candidate_keys(self):
        keys = fd.candidate_keys(ALL, self.fds)
        assert keys == [frozenset("AD")]

    def test_bcnf_violations(self):
        assert len(fd.bcnf_violations(ALL, self.fds)) == 2  # A→B and B→C


class TestGeneratorsMatchEngine:
    def test_closure_size(self):
        for seed in SEEDS:
            p = generate("fd_closure", "closure_size", {}, seed)
            fds = _parse(p.params)
            expected = len(fd.closure(frozenset(p.params["x"]), fds))
            assert p.correct_answer == float(expected)
            assert f"{p.correct_answer:.3f}" in p.choices
            # The folded worked solution shares the closed form: its last step
            # states the same count as the graded answer (ADR-0003).
            assert p.explain
            assert f"{expected} attribute" in p.explain[-1]

    def test_candidate_key_count(self):
        for seed in SEEDS:
            p = generate("candidate_keys", "count", {}, seed)
            fds = _parse(p.params)
            assert p.correct_answer == float(len(fd.candidate_keys(ALL, fds)))
            assert f"{p.correct_answer:.3f}" in p.choices

    def test_bcnf_violation_count(self):
        for seed in SEEDS:
            p = generate("bcnf_check", "violation_count", {}, seed)
            fds = _parse(p.params)
            assert p.correct_answer == float(len(fd.bcnf_violations(ALL, fds)))
            assert f"{p.correct_answer:.3f}" in p.choices
            assert f"Violation count = {int(p.correct_answer)}." in p.explain[-1]

    def test_every_kind_carries_a_worked_solution(self):
        # No solver registry for databases anymore — each generator must supply
        # its own explain, or the CLI/web would show no steps.
        for kind, ask in KINDS:
            p = generate(kind, ask, {}, 0)
            assert len(p.explain) >= 2, kind


class TestBuildItemUsesExplain:
    def _first_generator_concept(self, subject: str):
        from engine.db import dao
        return next(c for c in dao.get_concepts(subject) if c.mode == "generator")

    def test_migrated_subject_serves_generator_explain(self, db):
        import numpy as np

        from engine import service
        concept = self._first_generator_concept("databases")
        item = service.build_item(concept, np.random.default_rng(0))
        # databases has no solver registry; non-empty steps prove build_item took
        # the generator's own explain.
        assert item.explain

    def test_unmigrated_subject_falls_back_to_registry(self, db):
        import numpy as np

        from engine import service
        concept = self._first_generator_concept("diffeq")
        item = service.build_item(concept, np.random.default_rng(0))
        # diffeq still ships a solve.py; the fallback must still produce steps.
        assert item.explain
