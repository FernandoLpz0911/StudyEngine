"""Deterministic worked solutions for MATH 220 problems.

Recomputes each answer from the stored params using the same closed form as the
generator, then narrates the steps — so the explanation can never disagree with
the graded answer.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from engine.feedback.solve import register_solver


@dataclass
class Solved:
    steps: list[str]
    answer: float


@register_solver("separable_growth")
@register_solver("first_order_linear")
@register_solver("second_order_homog")
@register_solver("laplace_transform")
@register_solver("newton_cooling")
@register_solver("integrating_factor")
@register_solver("euler_method")
@register_solver("laplace_inverse")
def worked_steps(kind: str, ask: str, params: dict) -> list[str]:
    """Adapter so the central solver registry can reach the diffeq solutions."""
    return solve(kind, ask, params).steps


def solve(kind: str, ask: str, params: dict) -> Solved:
    dispatch = {
        "separable_growth": lambda: _separable_growth(params),
        "first_order_linear": lambda: _first_order_linear(ask, params),
        "second_order_homog": lambda: _second_order_homog(ask, params),
        "laplace_transform": lambda: _laplace_transform(ask, params),
        "newton_cooling": lambda: _newton_cooling(params),
        "integrating_factor": lambda: _integrating_factor(params),
        "euler_method": lambda: _euler_method(params),
        "laplace_inverse": lambda: _laplace_inverse(params),
    }
    if kind not in dispatch:
        raise ValueError(f"No solver for kind '{kind}'")
    return dispatch[kind]()


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


def _newton_cooling(p: dict) -> Solved:
    ts, t0, k, t1 = p["ts"], p["t0"], p["k"], p["t1"]
    answer = ts + (t0 - ts) * math.exp(-k * t1)
    steps = [
        "Newton's law of cooling: T(t) = Ts + (T0 − Ts)·e^(−kt).",
        f"Here Ts = {ts}, T0 = {t0}, k = {k}.",
        f"T({t1}) = {ts} + ({t0} − {ts})·e^(−{k}·{t1}) = {round(answer, 3)}.",
    ]
    return Solved(steps, round(answer, 3))


def _integrating_factor(p: dict) -> Solved:
    a, t0 = p["a"], p["t0"]
    answer = math.exp(a * t0)
    steps = [
        f"For y' + {a}·y = b, the integrating factor is μ(t) = e^(∫{a} dt) = e^({a}t).",
        f"Evaluate at t = {t0}: e^({a}·{t0}) = {round(answer, 3)}.",
    ]
    return Solved(steps, round(answer, 3))


def _euler_method(p: dict) -> Solved:
    a, b, y0, h = p["a"], p["b"], p["y0"], p["h"]
    y1 = y0 + h * (a * 0.0 + b * y0)
    y2 = y1 + h * (a * h + b * y1)
    steps = [
        f"Euler: y_{{n+1}} = y_n + h·f(x_n, y_n), with f(x,y) = {a}x + {b}y, h = {h}.",
        f"Step 1 (x=0): y1 = {y0} + {h}·({a}·0 + {b}·{y0}) = {round(y1, 3)}.",
        f"Step 2 (x={h}): y2 = {round(y1, 3)} + {h}·({a}·{h} + {b}·{round(y1, 3)}) "
        f"= {round(y2, 3)}.",
    ]
    return Solved(steps, round(y2, 3))


def _laplace_inverse(p: dict) -> Solved:
    t0 = p["t0"]
    family = p.get("family")
    if family == "exp":
        a = p["a"]
        answer = math.exp(a * t0)
        steps = [
            f"1/(s − {a}) is the transform of e^({a}t).",
            f"Evaluate at t = {t0}: e^({a}·{t0}) = {round(answer, 3)}.",
        ]
    elif family == "sin":
        w = p["w"]
        answer = math.sin(w * t0) / w
        steps = [
            f"1/(s² + {w**2}) inverts to sin({w}t)/{w}.",
            f"Evaluate at t = {t0}: sin({w}·{t0})/{w} = {round(answer, 3)} (radians).",
        ]
    else:
        w = p["w"]
        answer = math.cos(w * t0)
        steps = [
            f"s/(s² + {w**2}) inverts to cos({w}t).",
            f"Evaluate at t = {t0}: cos({w}·{t0}) = {round(answer, 3)} (radians).",
        ]
    return Solved(steps, round(answer, 3))
