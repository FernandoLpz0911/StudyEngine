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


# --- Full-syllabus expansion: every new kind/ask stays self-consistent ---
_NEW_ASKS = {
    "exact_equation": ["exactness_check", "potential_value"],
    "newtonian": ["terminal_velocity", "velocity_t"],
    "mixing": ["amount"],
    "population": ["exponential", "logistic"],
    "mass_spring": ["omega", "period", "damped_freq"],
    "char_complex": ["real_part", "imag_part"],
    "wronskian": ["value"],
    "undetermined": ["exp_coeff", "poly_const", "trig_amp"],
    "cauchy_euler": ["larger_root", "smaller_root"],
    "vibrations": ["damped_freq", "steady_amplitude"],
    "rlc": ["natural_freq", "damped_freq"],
    "rk4_step": ["one_step"],
    "system_eig": ["larger_eig", "smaller_eig"],
    "laplace_props": ["shift_value"],
    "laplace_ivp": ["value"],
    "step_function": ["transform_value"],
    "dirac_delta": ["transform_value", "impulse_response"],
    "fourier": ["b_n", "a_n"],
    "bvp_eigenvalue": ["lambda_n"],
    "heat_mode": ["value"],
    "wave_mode": ["value"],
}


def test_new_generators_self_consistent():
    """Generator answer ∈ choices, and the worked solver recomputes the same value."""
    for kind, asks in _NEW_ASKS.items():
        for ask in asks:
            for seed in SEEDS:
                p = generate(kind, ask, {}, seed)
                assert _choice_has_answer(p), (kind, ask, seed)
                assert solve(kind, ask, p.params).answer == p.correct_answer, (kind, ask)


class TestNewKeyFormulas:
    def test_terminal_velocity(self):
        for seed in SEEDS:
            p = generate("newtonian", "terminal_velocity", {}, seed)
            m, b = p.params["m"], p.params["bdrag"]
            assert p.correct_answer == round(m * 9.8 / b, 3)

    def test_bvp_eigenvalue(self):
        for seed in SEEDS:
            p = generate("bvp_eigenvalue", "lambda_n", {}, seed)
            n, ell = p.params["n"], p.params["ell"]
            assert p.correct_answer == round((n * math.pi / ell) ** 2, 3)

    def test_system_eigenvalue_larger(self):
        for seed in SEEDS:
            p = generate("system_eig", "larger_eig", {}, seed)
            a, b, c, dd = (p.params[x] for x in ("a", "b", "c", "d"))
            tr, det = a + dd, a * dd - b * c
            expected = (tr + math.sqrt(tr * tr - 4 * det)) / 2
            assert p.correct_answer == round(expected, 3)

    def test_fourier_bn(self):
        for seed in SEEDS:
            p = generate("fourier", "b_n", {}, seed)
            n, ell = p.params["n"], p.params["ell"]
            assert p.correct_answer == round(2 * ell / (n * math.pi) * (-1) ** (n + 1), 3)
