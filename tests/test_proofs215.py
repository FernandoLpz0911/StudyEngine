"""MATH 215 generator answer keys — recomputed independently across many seeds."""
from math import comb, factorial, gcd, perm

import engine.subjects  # noqa: F401  (registers generators)
from engine.feedback.solve import worked_solution
from engine.generation.base import generate

SEEDS = range(60)


def _check(kind, ask, expected_fn):
    """Assert correct_answer == expected, is in choices, and has a solution."""
    for seed in SEEDS:
        p = generate(kind, ask, {}, seed)
        assert p.correct_answer == float(expected_fn(p.params)), (kind, ask, p.params)
        assert f"{p.correct_answer:.3f}" in p.choices, (kind, ask, p.params)
        assert worked_solution(kind, ask, p.params), (kind, ask)


class TestSetCounting:
    def test_intersection(self):
        _check("set_counting", "intersection",
               lambda q: q["a"] + q["b"] - q["union"])

    def test_difference(self):
        _check("set_counting", "difference", lambda q: q["b"] - q["inter"])

    def test_offdiag(self):
        _check("set_counting", "offdiag", lambda q: q["n"] ** 2 - q["n"])

    def test_union2(self):
        _check("set_counting", "union2",
               lambda q: q["a"] + q["b"] - q["inter"])


class TestTruthTable:
    def test_count_true_3var_in_range(self):
        for seed in SEEDS:
            p = generate("truth_table", "count_true", {}, seed)
            assert 0 <= p.correct_answer <= 8
            assert f"{p.correct_answer:.3f}" in p.choices
            assert worked_solution("truth_table", "count_true", p.params)


class TestFunctionCount:
    def test_injections(self):
        _check("function_count", "injections",
               lambda q: perm(q["n"], q["m"]) if q["m"] <= q["n"] else 0)

    def test_bijections(self):
        _check("function_count", "bijections", lambda q: factorial(q["n"]))

    def test_count(self):
        _check("function_count", "count", lambda q: q["n"] ** q["m"])


class TestNumberTheory:
    def test_mod(self):
        _check("number_theory", "mod", lambda q: q["b"] % q["m"])

    def test_divides(self):
        _check("number_theory", "divides",
               lambda q: 1 if q["b"] % q["a"] == 0 else 0)

    def test_gcd(self):
        _check("number_theory", "gcd", lambda q: gcd(q["a"], q["b"]))

    def test_least_prime_factor(self):
        for seed in SEEDS:
            p = generate("number_theory", "least_prime_factor", {}, seed)
            n, lpf = p.params["n"], int(p.correct_answer)
            assert n % lpf == 0 and all(n % d for d in range(2, lpf))
            assert f"{p.correct_answer:.3f}" in p.choices


class TestModular:
    def test_add(self):
        _check("modular", "add", lambda q: (q["a"] + q["b"]) % q["m"])

    def test_mul(self):
        _check("modular", "mul", lambda q: (q["a"] * q["b"]) % q["m"])

    def test_pow(self):
        _check("modular", "pow", lambda q: pow(q["a"], q["k"], q["m"]))


class TestCombinatorics:
    def test_permutation(self):
        _check("combinatorics", "permutation", lambda q: perm(q["n"], q["r"]))

    def test_combination(self):
        _check("combinatorics", "combination", lambda q: comb(q["n"], q["r"]))

    def test_circular(self):
        _check("combinatorics", "circular", lambda q: factorial(q["n"] - 1))


class TestPigeonhole:
    def test_min_force(self):
        _check("pigeonhole", "min_force", lambda q: q["k"] + 1)

    def test_guaranteed(self):
        _check("pigeonhole", "guaranteed", lambda q: -(-q["n"] // q["k"]))


class TestInductionSum:
    def test_sum_i(self):
        _check("induction_sum", "sum_i", lambda q: q["n"] * (q["n"] + 1) // 2)

    def test_sum_i2(self):
        _check("induction_sum", "sum_i2",
               lambda q: q["n"] * (q["n"] + 1) * (2 * q["n"] + 1) // 6)

    def test_sum_cubes(self):
        _check("induction_sum", "sum_cubes",
               lambda q: (q["n"] * (q["n"] + 1) // 2) ** 2)

    def test_sum_odd(self):
        _check("induction_sum", "sum_odd", lambda q: q["n"] ** 2)


class TestFloor:
    def test_floor_val(self):
        _check("floor", "floor_val", lambda q: q["p"] // q["q"])

    def test_count_multiples(self):
        _check("floor", "count_multiples", lambda q: q["n"] // q["d"])
