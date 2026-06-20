"""FD engine correctness + answer keys for the CS 480 normalization generators."""
import engine.subjects  # noqa: F401  (registers generators + solvers)
from engine.feedback.solve import worked_solution
from engine.generation.base import generate
from engine.subjects.databases import fd

SEEDS = range(60)
ALL = frozenset("ABCD")


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
            assert worked_solution("fd_closure", "closure_size", p.params)

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
            assert worked_solution("bcnf_check", "violation_count", p.params)
