"""Deterministic worked solutions for MATH 220 problems.

Recomputes each answer from the stored params using the same closed form as the
generator, then narrates the steps — so the explanation can never disagree with
the graded answer.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Solved:
    steps: list[str]
    answer: float


def solve(kind: str, ask: str, params: dict) -> Solved:
    if kind == "separable_growth":
        return _separable_growth(params)
    if kind == "first_order_linear":
        return _first_order_linear(ask, params)
    if kind == "second_order_homog":
        return _second_order_homog(ask, params)
    if kind == "laplace_transform":
        return _laplace_transform(ask, params)
    raise ValueError(f"No solver for kind '{kind}'")


def _separable_growth(p: dict) -> Solved:
    y0, k, t1 = p["y0"], p["k"], p["t1"]
    answer = y0 * math.exp(k * t1)
    steps = [
        "Separate variables: dy/y = k·dt.",
        "Integrate both sides: ln|y| = k·t + C.",
        f"Exponentiate and apply y(0) = {y0}: y(t) = {y0}·e^({k}·t).",
        f"Evaluate at t = {t1}: y({t1}) = {y0}·e^({k}·{t1}) = {round(answer, 3)}.",
    ]
    return Solved(steps, round(answer, 3))


def _first_order_linear(ask: str, p: dict) -> Solved:
    a, b, y0, t1 = p["a"], p["b"], p["y0"], p["t1"]
    equilibrium = b / a
    if ask == "equilibrium":
        steps = [
            "At equilibrium y' = 0, so a·y = b.",
            f"Solve for y: y = b/a = {b}/{a} = {round(equilibrium, 3)}.",
        ]
        return Solved(steps, round(equilibrium, 3))
    answer = equilibrium + (y0 - equilibrium) * math.exp(-a * t1)
    steps = [
        f"This is linear with constant coefficients: y' + {a}·y = {b}.",
        f"Equilibrium (particular) solution: y_p = b/a = {round(equilibrium, 3)}.",
        f"General solution: y(t) = {round(equilibrium, 3)} + "
        f"(y0 − {round(equilibrium, 3)})·e^(−{a}·t).",
        f"Apply y(0) = {y0}, then evaluate at t = {t1}: y({t1}) = {round(answer, 3)}.",
    ]
    return Solved(steps, round(answer, 3))


def _second_order_homog(ask: str, p: dict) -> Solved:
    pp, qq, r1, r2 = p["p"], p["q"], p["r1"], p["r2"]
    answer = float(r2 if ask != "smaller_root" else r1)
    steps = [
        f"Write the characteristic equation: r² + ({pp})·r + ({qq}) = 0.",
        f"Factor: (r − {r1})·(r − {r2}) = 0.",
        f"Roots are r = {r1} and r = {r2}.",
        f"The {'smaller' if ask == 'smaller_root' else 'larger'} root is "
        f"{round(answer, 3)}.",
    ]
    return Solved(steps, round(answer, 3))


def _laplace_transform(ask: str, p: dict) -> Solved:
    s0 = p["s0"]
    if "a" in p:
        a = p["a"]
        answer = 1.0 / (s0 - a)
        steps = [
            f"L{{e^({a}t)}} = 1/(s − {a}).",
            f"Substitute s = {s0}: 1/({s0} − {a}) = {round(answer, 3)}.",
        ]
    elif "w" in p:
        w = p["w"]
        answer = s0 / (s0**2 + w**2)
        steps = [
            f"L{{cos({w}t)}} = s/(s² + {w**2}).",
            f"Substitute s = {s0}: {s0}/({s0}² + {w**2}) = {round(answer, 3)}.",
        ]
    else:
        n = p["n"]
        answer = math.factorial(n) / s0 ** (n + 1)
        steps = [
            f"L{{t^{n}}} = {n}!/s^{n + 1} = {math.factorial(n)}/s^{n + 1}.",
            f"Substitute s = {s0}: {math.factorial(n)}/{s0}^{n + 1} = {round(answer, 3)}.",
        ]
    return Solved(steps, round(answer, 3))
