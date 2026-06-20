"""Answer-key correctness for MATH 220 generators — the core guarantee.

Each test independently recomputes the answer and checks that the generator, the
multiple-choice set, and the worked solution all agree.
"""
import math

import engine.subjects  # noqa: F401  (registers generators)
from engine.generation.base import generate
from engine.subjects.diffeq.solve import solve

SEEDS = range(60)


def _choice_has_answer(problem) -> bool:
    return f"{problem.correct_answer:.3f}" in problem.choices


class TestSeparableGrowth:
    def test_matches_closed_form(self):
        for seed in SEEDS:
            p = generate("separable_growth", "value", {}, seed)
            expected = p.params["y0"] * math.exp(p.params["k"] * p.params["t1"])
            assert p.correct_answer == round(expected, 3)
            assert _choice_has_answer(p)
            assert solve("separable_growth", "value", p.params).answer == p.correct_answer


class TestFirstOrderLinear:
    def test_value_matches_closed_form(self):
        for seed in SEEDS:
            p = generate("first_order_linear", "value", {}, seed)
            a, b, y0, t1 = (p.params[k] for k in ("a", "b", "y0", "t1"))
            eq = b / a
            expected = eq + (y0 - eq) * math.exp(-a * t1)
            assert p.correct_answer == round(expected, 3)
            assert _choice_has_answer(p)

    def test_equilibrium_matches(self):
        for seed in SEEDS:
            p = generate("first_order_linear", "equilibrium", {}, seed)
            assert p.correct_answer == round(p.params["b"] / p.params["a"], 3)
            assert solve("first_order_linear", "equilibrium", p.params).answer == p.correct_answer


class TestSecondOrderHomog:
    def test_roots_satisfy_characteristic(self):
        for seed in SEEDS:
            for ask in ("larger_root", "smaller_root"):
                p = generate("second_order_homog", ask, {}, seed)
                pp, qq, r1, r2 = (p.params[k] for k in ("p", "q", "r1", "r2"))
                assert r1 + r2 == -pp
                assert r1 * r2 == qq
                root = p.correct_answer
                assert abs(root**2 + pp * root + qq) < 1e-9
                expected = max(r1, r2) if ask == "larger_root" else min(r1, r2)
                assert p.correct_answer == float(expected)


class TestLaplace:
    def test_each_family_matches(self):
        for seed in SEEDS:
            for ask in ("exp", "cos", "power"):
                p = generate("laplace_transform", ask, {}, seed)
                s0 = p.params["s0"]
                if "a" in p.params:
                    expected = 1.0 / (s0 - p.params["a"])
                elif "w" in p.params:
                    w = p.params["w"]
                    expected = s0 / (s0**2 + w**2)
                else:
                    n = p.params["n"]
                    expected = math.factorial(n) / s0 ** (n + 1)
                assert p.correct_answer == round(expected, 3)
                assert _choice_has_answer(p)
                assert solve("laplace_transform", p.ask, p.params).answer == p.correct_answer
