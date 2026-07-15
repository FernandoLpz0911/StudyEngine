"""Answer keys for the second batch of generators across all four subjects."""
import math

import engine.subjects  # noqa: F401  (registers generators + solvers)
from engine.feedback.solve import worked_solution
from engine.generation.base import generate
from engine.subjects.databases import fd
from engine.subjects.proofs.generators import _true_rows

SEEDS = range(60)
ALL = frozenset("ABCD")


def _has_answer(p) -> bool:
    return f"{p.correct_answer:.3f}" in p.choices


def _parse_fds(params):
    return [(frozenset(lhs), frozenset(rhs)) for lhs, rhs in params["fds"]]


class TestDiffEqNew:
    def test_newton_cooling(self):
        for seed in SEEDS:
            p = generate("newton_cooling", "temperature", {}, seed)
            ts, t0, k, t1 = (p.params[x] for x in ("ts", "t0", "k", "t1"))
            assert p.correct_answer == round(ts + (t0 - ts) * math.exp(-k * t1), 3)
            assert _has_answer(p)
            assert worked_solution("newton_cooling", "temperature", p.params)

    def test_integrating_factor(self):
        for seed in SEEDS:
            p = generate("integrating_factor", "factor_value", {}, seed)
            assert p.correct_answer == round(math.exp(p.params["a"] * p.params["t0"]), 3)
            assert _has_answer(p)

    def test_euler_method(self):
        for seed in SEEDS:
            p = generate("euler_method", "two_step", {}, seed)
            a, b, y0, h = (p.params[x] for x in ("a", "b", "y0", "h"))
            y1 = y0 + h * (a * 0.0 + b * y0)
            y2 = y1 + h * (a * h + b * y1)
            assert p.correct_answer == round(y2, 3)
            assert worked_solution("euler_method", "two_step", p.params)

    def test_laplace_inverse(self):
        for seed in SEEDS:
            for ask in ("exp", "sin", "cos"):
                p = generate("laplace_inverse", ask, {}, seed)
                t0 = p.params["t0"]
                if ask == "exp":
                    expected = math.exp(p.params["a"] * t0)
                elif ask == "sin":
                    expected = math.sin(p.params["w"] * t0) / p.params["w"]
                else:
                    expected = math.cos(p.params["w"] * t0)
                assert p.correct_answer == round(expected, 3)
                assert _has_answer(p)
                assert worked_solution("laplace_inverse", ask, p.params)


class TestDatabasesNew:
    def test_prime_attributes(self):
        for seed in SEEDS:
            p = generate("prime_attributes", "count", {}, seed)
            fds = _parse_fds(p.params)
            keys = fd.candidate_keys(ALL, fds)
            prime = set().union(*keys) if keys else set()
            assert p.correct_answer == float(len(prime))
            assert p.explain  # databases folds its worked solution (ADR-0003)

    def test_superkey_count(self):
        for seed in SEEDS:
            p = generate("superkey_count", "count", {}, seed)
            fds = _parse_fds(p.params)
            sets = [frozenset(s) for s in p.params["sets"]]
            expected = sum(fd.is_superkey(s, ALL, fds) for s in sets)
            assert p.correct_answer == float(expected)
            assert len(sets) == 4
            assert f"Count = {int(expected)}." in p.explain[-1]


class TestProofsNew:
    def test_cartesian(self):
        for seed in SEEDS:
            p = generate("set_counting", "cartesian", {}, seed)
            assert p.correct_answer == float(p.params["a"] * p.params["b"])
            assert _has_answer(p)

    def test_union3(self):
        for seed in SEEDS:
            p = generate("set_counting", "union3", {}, seed)
            q = p.params
            expected = (
                q["a"] + q["b"] + q["c"]
                - q["ab"] - q["ac"] - q["bc"] + q["triple"]
            )
            assert p.correct_answer == float(expected)
            assert worked_solution("set_counting", "union3", p.params)

    def test_truth_table(self):
        for seed in SEEDS:
            p = generate("truth_table", "true_rows", {}, seed)
            assert p.correct_answer == float(_true_rows(p.params["formula"]))
            assert 0 <= p.correct_answer <= 4
            assert worked_solution("truth_table", "true_rows", p.params)

    def test_function_count(self):
        for seed in SEEDS:
            p = generate("function_count", "count", {}, seed)
            assert p.correct_answer == float(p.params["n"] ** p.params["m"])
            assert _has_answer(p)


class TestEconNew:
    def test_percent_change(self):
        for seed in SEEDS:
            p = generate("econ_decision", "percent_change", {}, seed)
            old, new = p.params["old"], p.params["new"]
            assert p.correct_answer == round((new - old) / old * 100, 2)
            assert worked_solution("econ_decision", "percent_change", p.params)

    def test_roi(self):
        for seed in SEEDS:
            p = generate("econ_decision", "roi", {}, seed)
            cost, gain = p.params["cost"], p.params["gain"]
            assert p.correct_answer == round((gain - cost) / cost * 100, 2)

    def test_elasticity(self):
        for seed in SEEDS:
            p = generate("econ_decision", "elasticity", {}, seed)
            dq, dp = p.params["dq"], p.params["dp"]
            assert p.correct_answer == round(abs(dq / dp), 2)
            assert worked_solution("econ_decision", "elasticity", p.params)
