"""MATH 220 problem generators — closed-form ODE and Laplace problems.

Every answer is computed in closed form, so the graded value and the worked
solution (engine.subjects.diffeq.solve) share one source of truth.
"""
from __future__ import annotations

import math

import numpy as np

from engine.generation.base import Problem, make_mc_choices, register


@register("separable_growth")
def gen_separable_growth(ask: str, params: dict, seed: int) -> Problem:
    """dy/dt = k·y, y(0) = y0  →  y(t) = y0·e^{k t}. Find y(t1)."""
    rng = np.random.default_rng(seed)
    y0 = round(float(rng.uniform(2, 10)), 1)
    k = round(float(rng.uniform(-0.8, 0.8)), 2)
    if abs(k) < 0.15:
        k = 0.3
    t1 = int(rng.integers(1, 5))

    answer = y0 * math.exp(k * t1)
    wrongs = [
        y0 * math.exp(-k * t1),   # sign error in the exponent
        y0 * (1 + k * t1),        # linear (first-order Taylor) approximation
        y0,                       # forgot to evolve in time
    ]
    statement = (
        f"Solve dy/dt = {k}·y with y(0) = {y0}. Find y({t1}). Round to 3 decimals."
    )
    return Problem(
        "separable_growth", "value", statement, round(answer, 3),
        make_mc_choices(answer, wrongs, rng),
        params={"y0": y0, "k": k, "t1": t1}, seed=seed,
    )


@register("first_order_linear")
def gen_first_order_linear(ask: str, params: dict, seed: int) -> Problem:
    """y' + a·y = b, y(0) = y0  →  y(t) = b/a + (y0 - b/a)·e^{-a t}."""
    rng = np.random.default_rng(seed)
    a = round(float(rng.uniform(0.3, 1.5)), 2)
    b = round(float(rng.uniform(1, 6)), 1)
    y0 = round(float(rng.uniform(0, 8)), 1)
    t1 = int(rng.integers(1, 5))
    equilibrium = b / a

    if ask == "equilibrium":
        answer = equilibrium
        wrongs = [a / b, b * a, b - a]
        statement = (
            f"For y' + {a}·y = {b}, find the equilibrium solution "
            f"(the constant value y approaches as t → ∞)."
        )
    else:
        ask = "value"
        answer = equilibrium + (y0 - equilibrium) * math.exp(-a * t1)
        wrongs = [
            equilibrium,                                    # ignored the transient
            equilibrium + (y0 - equilibrium) * math.exp(a * t1),  # sign error
            y0 * math.exp(-a * t1),                         # dropped the forcing term
        ]
        statement = (
            f"Solve y' + {a}·y = {b} with y(0) = {y0}. Find y({t1}). "
            f"Round to 3 decimals."
        )
    return Problem(
        "first_order_linear", ask, statement, round(answer, 3),
        make_mc_choices(answer, wrongs, rng),
        params={"a": a, "b": b, "y0": y0, "t1": t1}, seed=seed,
    )


@register("second_order_homog")
def gen_second_order_homog(ask: str, params: dict, seed: int) -> Problem:
    """y'' + p·y' + q·y = 0 with real distinct roots r1 < r2 (built from integer roots)."""
    rng = np.random.default_rng(seed)
    roots = sorted(
        int(r) for r in rng.choice([-4, -3, -2, -1, 1, 2, 3], size=2, replace=False)
    )
    r1, r2 = roots
    p = -(r1 + r2)
    q = r1 * r2

    if ask == "smaller_root":
        answer = float(r1)
        which = "smaller"
    else:
        ask = "larger_root"
        answer = float(r2)
        which = "larger"
    wrongs = [float(-r2), float(-r1), float(p), float(q)]
    statement = (
        f"For y'' + ({p})·y' + ({q})·y = 0, find the {which} root of the "
        f"characteristic equation r² + ({p})·r + ({q}) = 0."
    )
    return Problem(
        "second_order_homog", ask, statement, round(answer, 3),
        make_mc_choices(answer, wrongs, rng),
        params={"p": p, "q": q, "r1": r1, "r2": r2}, seed=seed,
    )


@register("laplace_transform")
def gen_laplace_transform(ask: str, params: dict, seed: int) -> Problem:
    """Evaluate a standard Laplace transform F(s) at a given s0."""
    rng = np.random.default_rng(seed)
    family = ask if ask in ("exp", "cos", "power") else str(
        rng.choice(["exp", "cos", "power"])
    )

    if family == "exp":
        a = int(rng.integers(1, 4))
        s0 = a + int(rng.integers(1, 4))
        answer = 1.0 / (s0 - a)
        wrongs = [1.0 / (s0 + a), float(s0 - a), 1.0 / s0]
        statement = (
            f"f(t) = e^({a}t). Its Laplace transform is F(s) = 1/(s − {a}). "
            f"Evaluate F({s0}). Round to 3 decimals."
        )
        extra = {"a": a, "s0": s0}
    elif family == "cos":
        w = int(rng.integers(1, 4))
        s0 = int(rng.integers(1, 5))
        answer = s0 / (s0**2 + w**2)
        wrongs = [
            w / (s0**2 + w**2),         # used w instead of s in the numerator
            (s0 + w) / (s0**2 + w**2),  # added the frequency into the numerator
            1.0 / (s0**2 + w**2),       # dropped the s in the numerator
        ]
        statement = (
            f"f(t) = cos({w}t). Its Laplace transform is F(s) = s/(s² + {w**2}). "
            f"Evaluate F({s0}). Round to 3 decimals."
        )
        extra = {"w": w, "s0": s0}
    else:
        n = int(rng.integers(1, 4))
        s0 = int(rng.integers(2, 5))
        answer = math.factorial(n) / s0 ** (n + 1)
        wrongs = [
            math.factorial(n) / s0**n,          # wrong power of s
            1.0 / s0 ** (n + 1),                # forgot n!
            (n + 1) / s0 ** (n + 1),            # used (n+1) instead of n!
        ]
        statement = (
            f"f(t) = t^{n}. Its Laplace transform is F(s) = {math.factorial(n)}/s^{n + 1}. "
            f"Evaluate F({s0}). Round to 3 decimals."
        )
        extra = {"n": n, "s0": s0}

    return Problem(
        "laplace_transform", family, statement, round(answer, 3),
        make_mc_choices(answer, wrongs, rng),
        params=extra, seed=seed,
    )


@register("newton_cooling")
def gen_newton_cooling(ask: str, params: dict, seed: int) -> Problem:
    """Newton's law of cooling: T(t) = Ts + (T0 − Ts)·e^{−k t}."""
    rng = np.random.default_rng(seed)
    ts = round(float(rng.uniform(15, 25)), 1)
    t0 = round(float(rng.uniform(60, 95)), 1)
    k = round(float(rng.uniform(0.2, 0.9)), 2)
    t1 = int(rng.integers(1, 5))

    answer = ts + (t0 - ts) * math.exp(-k * t1)
    wrongs = [
        ts,                                   # equilibrium (ignored the transient)
        t0,                                   # initial temperature
        ts + (t0 - ts) * math.exp(k * t1),    # sign error in the exponent
    ]
    statement = (
        f"An object at {t0}° cools in surroundings of {ts}° with rate k = {k}. "
        f"Newton's law gives T(t) = {ts} + ({t0} − {ts})·e^(−{k}t). Find T({t1}). "
        f"Round to 3 decimals."
    )
    return Problem(
        "newton_cooling", "temperature", statement, round(answer, 3),
        make_mc_choices(answer, wrongs, rng),
        params={"ts": ts, "t0": t0, "k": k, "t1": t1}, seed=seed,
    )


@register("integrating_factor")
def gen_integrating_factor(ask: str, params: dict, seed: int) -> Problem:
    """Integrating factor of y' + a·y = b is μ(t) = e^{a t}; evaluate at t0."""
    rng = np.random.default_rng(seed)
    a = round(float(rng.uniform(0.3, 1.5)), 2)
    b = round(float(rng.uniform(1, 6)), 1)
    t0 = int(rng.integers(1, 4))

    answer = math.exp(a * t0)
    wrongs = [math.exp(-a * t0), float(a * t0), math.exp(a)]
    statement = (
        f"For y' + {a}·y = {b}, the integrating factor is μ(t) = e^(∫{a} dt) = "
        f"e^({a}t). Evaluate μ({t0}). Round to 3 decimals."
    )
    return Problem(
        "integrating_factor", "factor_value", statement, round(answer, 3),
        make_mc_choices(answer, wrongs, rng),
        params={"a": a, "b": b, "t0": t0}, seed=seed,
    )


@register("euler_method")
def gen_euler_method(ask: str, params: dict, seed: int) -> Problem:
    """Two steps of Euler's method on y' = a·x + b·y from x = 0."""
    rng = np.random.default_rng(seed)
    a = round(float(rng.uniform(0.5, 2.0)), 1)
    b = round(float(rng.uniform(-0.5, 0.8)), 2)
    y0 = round(float(rng.uniform(1, 5)), 1)
    h = round(float(rng.choice([0.1, 0.2, 0.5])), 1)

    y1 = y0 + h * (a * 0.0 + b * y0)
    y2 = y1 + h * (a * h + b * y1)
    wrongs = [y1, y0, y0 + h * a]
    statement = (
        f"Use Euler's method on y' = {a}x + {b}y with y(0) = {y0} and step "
        f"h = {h}. Estimate y after two steps (at x = {round(2 * h, 3)}). "
        f"Round to 3 decimals."
    )
    return Problem(
        "euler_method", "two_step", statement, round(y2, 3),
        make_mc_choices(y2, wrongs, rng),
        params={"a": a, "b": b, "y0": y0, "h": h}, seed=seed,
    )


@register("laplace_inverse")
def gen_laplace_inverse(ask: str, params: dict, seed: int) -> Problem:
    """Invert a standard transform F(s) → f(t), then evaluate f at t0."""
    rng = np.random.default_rng(seed)
    family = ask if ask in ("exp", "sin", "cos") else str(
        rng.choice(["exp", "sin", "cos"])
    )
    t0 = int(rng.integers(1, 4))

    if family == "exp":
        a = int(rng.integers(1, 4))
        answer = math.exp(a * t0)
        wrongs = [math.exp(-a * t0), float(a * t0), 1.0 / (t0 - a) if t0 != a else 0.0]
        statement = (
            f"F(s) = 1/(s − {a}) inverts to f(t) = e^({a}t). Find f({t0}). "
            f"Round to 3 decimals."
        )
        extra = {"a": a, "t0": t0, "family": family}
    elif family == "sin":
        w = int(rng.integers(1, 4))
        answer = math.sin(w * t0) / w
        wrongs = [math.sin(w * t0), math.cos(w * t0) / w, w * math.sin(w * t0)]
        statement = (
            f"F(s) = 1/(s² + {w**2}) inverts to f(t) = sin({w}t)/{w}. "
            f"Find f({t0}). Round to 3 decimals (t in radians)."
        )
        extra = {"w": w, "t0": t0, "family": family}
    else:
        w = int(rng.integers(1, 4))
        answer = math.cos(w * t0)
        wrongs = [math.sin(w * t0), -math.cos(w * t0), math.cos(t0)]
        statement = (
            f"F(s) = s/(s² + {w**2}) inverts to f(t) = cos({w}t). Find f({t0}). "
            f"Round to 3 decimals (t in radians)."
        )
        extra = {"w": w, "t0": t0, "family": family}

    return Problem(
        "laplace_inverse", family, statement, round(answer, 3),
        make_mc_choices(answer, wrongs, rng),
        params=extra, seed=seed,
    )
