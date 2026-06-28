"""MATH 220 problem generators — closed-form ODE and Laplace problems.

Every answer is computed in closed form, so the graded value and the worked
solution (engine.subjects.diffeq.solve) share one source of truth.
"""
from __future__ import annotations

import math

import numpy as np

from engine.generation.base import Problem, make_mc_choices, register


def _p(kind, fam, stmt, ans, wrongs, extra, seed, rng):
    return Problem(kind, fam, stmt, round(ans, 3),
                   make_mc_choices(ans, wrongs, rng), params=extra, seed=seed)


def _binary(ans, rng):
    opts = [f"{float(ans):.3f}", f"{float(1 - ans):.3f}"]
    return [opts[i] for i in rng.permutation(2)]


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


@register("exact_equation")
def gen_exact(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    a = int(rng.integers(1, 5))
    b = int(rng.integers(1, 4))
    c = int(rng.integers(1, 4))
    if ask == "potential_value":
        x0, y0 = int(rng.integers(1, 4)), int(rng.integers(1, 4))
        answer = a * x0 * y0 + b * x0 * x0 + c * y0 * y0
        stmt = (
            f"The exact equation M dx + N dy = 0 with M = {a}y + {2 * b}x, "
            f"N = {a}x + {2 * c}y has potential F(x,y) = {a}xy + {b}x² + {c}y² "
            f"(solutions F = C). Evaluate F({x0}, {y0})."
        )
        wrongs = [a * x0 * y0, b * x0 * x0 + c * y0 * y0, a * x0 * y0 + b * x0 + c * y0]
        return _p("exact_equation", "potential_value", stmt, float(answer),
                  wrongs, {"a": a, "b": b, "c": c, "x0": x0, "y0": y0}, seed, rng)
    aa = a if rng.random() < 0.5 else a + int(rng.integers(1, 3))
    answer = 1.0 if a == aa else 0.0
    stmt = (
        f"For M dx + N dy = 0 with M = {a}y + {2 * b}x and N = {aa}x + {2 * c}y, "
        f"is the equation exact? Compare ∂M/∂y and ∂N/∂x. (1 = yes, 0 = no)"
    )
    return Problem("exact_equation", "exactness_check", stmt, round(answer, 3),
                   _binary(answer, rng),
                   params={"a": a, "aa": aa, "b": b, "c": c}, seed=seed)


@register("newtonian")
def gen_newtonian(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    m = int(rng.integers(1, 6))
    g = 9.8
    bdrag = round(float(rng.uniform(0.5, 3.0)), 2)
    term = m * g / bdrag
    if ask == "velocity_t":
        t1 = int(rng.integers(1, 6))
        answer = term * (1 - math.exp(-bdrag / m * t1))
        stmt = (
            f"A {m} kg body falls under gravity (g = 9.8) with linear drag, "
            f"m·v' = m·g − {bdrag}·v, v(0) = 0. Find the speed v({t1}). "
            f"Round to 3 decimals."
        )
        wrongs = [term, g * t1, term * (1 - math.exp(-bdrag * t1))]
        return _p("newtonian", "velocity_t", stmt, answer, wrongs,
                  {"m": m, "bdrag": bdrag, "t1": t1}, seed, rng)
    answer = term
    stmt = (
        f"A {m} kg body falls with linear drag m·v' = m·g − {bdrag}·v "
        f"(g = 9.8). Find the terminal velocity (v as t → ∞). Round to 3 decimals."
    )
    wrongs = [bdrag / (m * g), m * g, m * g * bdrag]
    return _p("newtonian", "terminal_velocity", stmt, answer, wrongs,
              {"m": m, "bdrag": bdrag}, seed, rng)


@register("mixing")
def gen_mixing(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    vol = int(rng.integers(50, 201))
    cin = round(float(rng.uniform(0.1, 1.0)), 2)
    r = int(rng.integers(2, 11))
    a0 = round(float(rng.uniform(0, 30)), 1)
    t1 = int(rng.integers(1, 7))
    eq = vol * cin
    answer = eq + (a0 - eq) * math.exp(-(r / vol) * t1)
    stmt = (
        f"A tank holds {vol} L of brine. Solution with {cin} kg/L enters at "
        f"{r} L/min and the well-mixed solution leaves at {r} L/min; initial salt "
        f"is {a0} kg. The amount obeys A' = {cin}·{r} − ({r}/{vol})·A. "
        f"Find A({t1}) min. Round to 3 decimals."
    )
    wrongs = [eq, a0, eq + (a0 - eq) * math.exp((r / vol) * t1)]
    return _p("mixing", "amount", stmt, answer, wrongs,
              {"vol": vol, "cin": cin, "r": r, "a0": a0, "t1": t1}, seed, rng)


@register("population")
def gen_population(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    p0 = round(float(rng.uniform(10, 80)), 1)
    r = round(float(rng.uniform(0.05, 0.4)), 2)
    t1 = int(rng.integers(1, 7))
    if ask == "logistic":
        k = round(float(rng.uniform(150, 400)), 0)
        answer = k / (1 + (k - p0) / p0 * math.exp(-r * t1))
        stmt = (
            f"A logistic population P' = {r}·P·(1 − P/{k:.0f}) has P(0) = {p0}. "
            f"Find P({t1}). Round to 3 decimals."
        )
        wrongs = [p0 * math.exp(r * t1), k, p0 * (1 + r * t1)]
        return _p("population", "logistic", stmt, answer, wrongs,
                  {"p0": p0, "r": r, "k": k, "t1": t1}, seed, rng)
    answer = p0 * math.exp(r * t1)
    stmt = (
        f"A population grows exponentially, P' = {r}·P, with P(0) = {p0}. "
        f"Find P({t1}). Round to 3 decimals."
    )
    wrongs = [p0 * (1 + r * t1), p0 * math.exp(-r * t1), p0]
    return _p("population", "exponential", stmt, answer, wrongs,
              {"p0": p0, "r": r, "t1": t1}, seed, rng)


@register("mass_spring")
def gen_mass_spring(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    m = int(rng.integers(1, 6))
    k = int(rng.integers(2, 40))
    omega = math.sqrt(k / m)
    if ask == "period":
        answer = 2 * math.pi / omega
        stmt = (
            f"An undamped mass-spring system has mass m = {m} and stiffness "
            f"k = {k} (m·x'' + k·x = 0). Find the period 2π/ω. Round to 3 decimals."
        )
        wrongs = [omega, 1 / omega, math.pi / omega]
        return _p("mass_spring", "period", stmt, answer, wrongs,
                  {"m": m, "k": k}, seed, rng)
    if ask == "damped_freq":
        c = round(float(rng.uniform(0.2, 1.5)), 2)
        disc = k / m - (c / (2 * m)) ** 2
        while disc <= 0.01:
            c = round(c / 2, 2)
            disc = k / m - (c / (2 * m)) ** 2
        answer = math.sqrt(disc)
        stmt = (
            f"A damped oscillator m·x'' + c·x' + k·x = 0 has m = {m}, c = {c}, "
            f"k = {k}. Find the damped angular frequency "
            f"√(k/m − (c/2m)²). Round to 3 decimals."
        )
        wrongs = [omega, math.sqrt(k / m + (c / (2 * m)) ** 2), c / (2 * m)]
        return _p("mass_spring", "damped_freq", stmt, answer, wrongs,
                  {"m": m, "k": k, "c": c}, seed, rng)
    answer = omega
    stmt = (
        f"An undamped mass-spring system has mass m = {m} and stiffness k = {k} "
        f"(m·x'' + k·x = 0). Find the natural angular frequency ω = √(k/m). "
        f"Round to 3 decimals."
    )
    wrongs = [k / m, math.sqrt(m / k), 2 * math.pi * math.sqrt(k / m)]
    return _p("mass_spring", "omega", stmt, answer, wrongs,
              {"m": m, "k": k}, seed, rng)


@register("char_complex")
def gen_char_complex(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    alpha = int(rng.integers(-3, 4))
    beta = int(rng.integers(1, 5))
    p = -2 * alpha
    q = alpha * alpha + beta * beta
    if ask == "imag_part":
        answer = float(beta)
        stmt = (
            f"y'' + ({p})·y' + ({q})·y = 0 has complex roots α ± βi. Find β "
            f"(the imaginary part), from r² + ({p})r + ({q}) = 0. Round to 3 decimals."
        )
        wrongs = [float(alpha), float(-p / 2), float(2 * beta)]
        return _p("char_complex", "imag_part", stmt, answer, wrongs,
                  {"p": p, "q": q, "alpha": alpha, "beta": beta}, seed, rng)
    answer = float(alpha)
    stmt = (
        f"y'' + ({p})·y' + ({q})·y = 0 has complex roots α ± βi. Find α "
        f"(the real part) from r² + ({p})r + ({q}) = 0. Round to 3 decimals."
    )
    wrongs = [float(beta), float(p / 2), float(-alpha)]
    return _p("char_complex", "real_part", stmt, answer, wrongs,
              {"p": p, "q": q, "alpha": alpha, "beta": beta}, seed, rng)


@register("wronskian")
def gen_wronskian(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    r1, r2 = sorted(int(x) for x in rng.choice([-2, -1, 1, 2, 3], size=2,
                                               replace=False))
    t0 = int(rng.integers(0, 3))
    answer = (r2 - r1) * math.exp((r1 + r2) * t0)
    stmt = (
        f"For the solutions y₁ = e^({r1}t) and y₂ = e^({r2}t), the Wronskian is "
        f"W = (r₂ − r₁)·e^((r₁+r₂)t). Evaluate W at t = {t0}. Round to 3 decimals."
    )
    wrongs = [(r1 - r2) * math.exp((r1 + r2) * t0), float(r2 - r1),
              (r2 - r1) * math.exp((r1 * r2) * t0)]
    return _p("wronskian", "value", stmt, answer, wrongs,
              {"r1": r1, "r2": r2, "t0": t0}, seed, rng)


@register("undetermined")
def gen_undetermined(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    p = int(rng.integers(1, 6))
    q = int(rng.integers(2, 12))
    if ask == "trig_amp":
        w = int(rng.integers(1, 4))
        f0 = int(rng.integers(2, 9))
        denom = q - w * w
        while denom == 0:
            w += 1
            denom = q - w * w
        answer = f0 / denom
        stmt = (
            f"For y'' + {q}·y = {f0}·cos({w}t), the particular solution is "
            f"y_p = A·cos({w}t) with A = F₀/(q − ω²). Find A. Round to 3 decimals."
        )
        wrongs = [f0 / (q + w * w), f0 / q, float(f0)]
        return _p("undetermined", "trig_amp", stmt, answer, wrongs,
                  {"q": q, "w": w, "f0": f0}, seed, rng)
    if ask == "poly_const":
        c = int(rng.integers(2, 12))
        answer = c / q
        stmt = (
            f"For y'' + {p}·y' + {q}·y = {c}, the particular solution is a "
            f"constant y_p = C/q. Find it. Round to 3 decimals."
        )
        wrongs = [float(c), c / p, c * q]
        return _p("undetermined", "poly_const", stmt, answer, wrongs,
                  {"p": p, "q": q, "c": c}, seed, rng)
    r = int(rng.integers(1, 5))
    amp = int(rng.integers(2, 9))
    denom = r * r + p * r + q
    answer = amp / denom
    stmt = (
        f"For y'' + {p}·y' + {q}·y = {amp}·e^({r}t), try y_p = A·e^({r}t). "
        f"Then A = F₀/(r² + p·r + q). Find A. Round to 3 decimals."
    )
    wrongs = [float(amp), amp / q, amp / (r * r)]
    return _p("undetermined", "exp_coeff", stmt, answer, wrongs,
              {"p": p, "q": q, "r": r, "amp": amp}, seed, rng)


@register("cauchy_euler")
def gen_cauchy_euler(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    r1, r2 = sorted(int(x) for x in rng.choice([-3, -2, -1, 1, 2, 3], size=2,
                                               replace=False))
    b = 1 - (r1 + r2)
    c = r1 * r2
    if ask == "smaller_root":
        answer, which = float(r1), "smaller"
    else:
        ask, answer, which = "larger_root", float(r2), "larger"
    stmt = (
        f"The Cauchy–Euler equation x²y'' + ({b})·x·y' + ({c})·y = 0 has indicial "
        f"equation r² + ({b - 1})·r + ({c}) = 0 (from r(r−1) + {b}r + {c}). Find "
        f"the {which} root. Round to 3 decimals."
    )
    wrongs = [float(-r1), float(-r2), float(b)]
    return _p("cauchy_euler", ask, stmt, answer, wrongs,
              {"b": b, "c": c, "r1": r1, "r2": r2}, seed, rng)


@register("vibrations")
def gen_vibrations(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    m = int(rng.integers(1, 5))
    k = int(rng.integers(4, 40))
    if ask == "steady_amplitude":
        c = round(float(rng.uniform(0.5, 3.0)), 2)
        w = round(float(rng.uniform(0.5, 4.0)), 2)
        f0 = int(rng.integers(2, 12))
        answer = f0 / math.sqrt((k - m * w * w) ** 2 + (c * w) ** 2)
        stmt = (
            f"A forced oscillator m·x'' + c·x' + k·x = F₀·cos(ωt) has m = {m}, "
            f"c = {c}, k = {k}, F₀ = {f0}, ω = {w}. The steady-state amplitude is "
            f"F₀/√((k − mω²)² + (cω)²). Find it. Round to 3 decimals."
        )
        wrongs = [f0 / k, float(f0), f0 / abs(k - m * w * w)]
        return _p("vibrations", "steady_amplitude", stmt, answer, wrongs,
                  {"m": m, "k": k, "c": c, "w": w, "f0": f0}, seed, rng)
    c = round(float(rng.uniform(0.3, 2.0)), 2)
    disc = k / m - (c / (2 * m)) ** 2
    while disc <= 0.01:
        c = round(c / 2, 2)
        disc = k / m - (c / (2 * m)) ** 2
    answer = math.sqrt(disc)
    stmt = (
        f"An underdamped oscillator m·x'' + c·x' + k·x = 0 has m = {m}, c = {c}, "
        f"k = {k}. Find the damped frequency ω_d = √(k/m − (c/2m)²). "
        f"Round to 3 decimals."
    )
    wrongs = [math.sqrt(k / m), c / (2 * m), math.sqrt(k / m + (c / (2 * m)) ** 2)]
    return _p("vibrations", "damped_freq", stmt, answer, wrongs,
              {"m": m, "k": k, "c": c}, seed, rng)


@register("rlc")
def gen_rlc(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    cap = round(float(rng.uniform(0.05, 0.5)), 2)
    ind = round(float(rng.uniform(0.5, 4.0)), 2)
    omega0 = 1 / math.sqrt(ind * cap)
    if ask == "damped_freq":
        res = round(float(rng.uniform(0.2, 1.5)), 2)
        disc = 1 / (ind * cap) - (res / (2 * ind)) ** 2
        while disc <= 0.01:
            res = round(res / 2, 2)
            disc = 1 / (ind * cap) - (res / (2 * ind)) ** 2
        answer = math.sqrt(disc)
        stmt = (
            f"An RLC circuit L·q'' + R·q' + q/C = 0 has L = {ind}, R = {res}, "
            f"C = {cap}. Find the damped frequency √(1/(LC) − (R/2L)²). "
            f"Round to 3 decimals."
        )
        wrongs = [omega0, res / (2 * ind), 1 / (ind * cap)]
        return _p("rlc", "damped_freq", stmt, answer, wrongs,
                  {"ind": ind, "res": res, "cap": cap}, seed, rng)
    answer = omega0
    stmt = (
        f"An LC circuit L·q'' + q/C = 0 has L = {ind}, C = {cap}. Find the natural "
        f"angular frequency ω₀ = 1/√(LC). Round to 3 decimals."
    )
    wrongs = [math.sqrt(ind * cap), 1 / (ind * cap), ind * cap]
    return _p("rlc", "natural_freq", stmt, answer, wrongs,
              {"ind": ind, "cap": cap}, seed, rng)


@register("rk4_step")
def gen_rk4_step(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    lam = round(float(rng.uniform(-0.6, 0.8)), 2)
    if abs(lam) < 0.15:
        lam = 0.3
    y0 = round(float(rng.uniform(1, 6)), 1)
    h = round(float(rng.choice([0.1, 0.2, 0.5])), 1)
    k1 = lam * y0
    k2 = lam * (y0 + h * k1 / 2)
    k3 = lam * (y0 + h * k2 / 2)
    k4 = lam * (y0 + h * k3)
    answer = y0 + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    stmt = (
        f"Take one RK4 step of y' = {lam}·y with y(0) = {y0} and step h = {h}. "
        f"Estimate y({h}). Round to 3 decimals."
    )
    wrongs = [y0 + h * k1, y0 * math.exp(lam * h), y0]
    return _p("rk4_step", "one_step", stmt, answer, wrongs,
              {"lam": lam, "y0": y0, "h": h}, seed, rng)


@register("system_eig")
def gen_system_eig(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    while True:
        a, b, c, d = (int(rng.integers(-3, 4)) for _ in range(4))
        tr = a + d
        det = a * d - b * c
        disc = tr * tr - 4 * det
        if disc > 0:
            break
    root = math.sqrt(disc)
    larger = (tr + root) / 2
    smaller = (tr - root) / 2
    if ask == "smaller_eig":
        answer, which = smaller, "smaller"
    else:
        ask, answer, which = "larger_eig", larger, "larger"
    stmt = (
        f"The linear system x' = A·x has A = [[{a}, {b}], [{c}, {d}]]. Find the "
        f"{which} eigenvalue (λ = (tr ± √(tr²−4·det))/2). Round to 3 decimals."
    )
    wrongs = [float(tr), float(det), -answer]
    return _p("system_eig", ask, stmt, answer, wrongs,
              {"a": a, "b": b, "c": c, "d": d}, seed, rng)


@register("laplace_props")
def gen_laplace_props(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    a = int(rng.integers(1, 4))
    w = int(rng.integers(1, 4))
    s0 = a + int(rng.integers(1, 4))
    answer = (s0 - a) / ((s0 - a) ** 2 + w * w)
    stmt = (
        f"By the first shifting theorem, L{{e^({a}t)·cos({w}t)}} = "
        f"(s − {a})/((s − {a})² + {w * w}). Evaluate at s = {s0}. "
        f"Round to 3 decimals."
    )
    wrongs = [s0 / (s0 * s0 + w * w), 1 / (s0 - a),
              (s0 + a) / ((s0 + a) ** 2 + w * w)]
    return _p("laplace_props", "shift_value", stmt, answer, wrongs,
              {"a": a, "w": w, "s0": s0}, seed, rng)


@register("laplace_ivp")
def gen_laplace_ivp(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    a = round(float(rng.uniform(0.3, 1.5)), 2)
    y0 = round(float(rng.uniform(1, 8)), 1)
    t1 = int(rng.integers(1, 5))
    answer = y0 * math.exp(-a * t1)
    stmt = (
        f"Solve y' + {a}·y = 0, y(0) = {y0} by Laplace transforms: "
        f"(sY − {y0}) + {a}Y = 0 ⇒ Y = {y0}/(s + {a}) ⇒ y(t) = {y0}·e^(−{a}t). "
        f"Find y({t1}). Round to 3 decimals."
    )
    wrongs = [y0 * math.exp(a * t1), y0, y0 / (1 + a * t1)]
    return _p("laplace_ivp", "value", stmt, answer, wrongs,
              {"a": a, "y0": y0, "t1": t1}, seed, rng)


@register("step_function")
def gen_step_function(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    a = int(rng.integers(1, 5))
    s0 = int(rng.integers(1, 5))
    answer = math.exp(-a * s0) / s0
    stmt = (
        f"The Heaviside step u(t − {a}) has Laplace transform "
        f"L{{u(t − {a})}} = e^(−{a}s)/s. Evaluate at s = {s0}. Round to 3 decimals."
    )
    wrongs = [math.exp(-a * s0), 1 / s0, math.exp(a * s0) / s0]
    return _p("step_function", "transform_value", stmt, answer, wrongs,
              {"a": a, "s0": s0}, seed, rng)


@register("dirac_delta")
def gen_dirac_delta(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    a = int(rng.integers(1, 5))
    if ask == "impulse_response":
        coef = round(float(rng.uniform(0.3, 1.5)), 2)
        t1 = int(rng.integers(1, 5))
        answer = math.exp(-coef * t1)
        stmt = (
            f"The impulse response of y' + {coef}·y = δ(t), y(0⁻) = 0, is "
            f"y(t) = e^(−{coef}t). Find y({t1}). Round to 3 decimals."
        )
        wrongs = [math.exp(coef * t1), 1.0, coef * math.exp(-coef * t1)]
        return _p("dirac_delta", "impulse_response", stmt, answer, wrongs,
                  {"coef": coef, "t1": t1}, seed, rng)
    s0 = int(rng.integers(1, 5))
    answer = math.exp(-a * s0)
    stmt = (
        f"The Dirac delta δ(t − {a}) has Laplace transform "
        f"L{{δ(t − {a})}} = e^(−{a}s). Evaluate at s = {s0}. Round to 3 decimals."
    )
    wrongs = [math.exp(a * s0), math.exp(-a * s0) / s0, 1.0]
    return _p("dirac_delta", "transform_value", stmt, answer, wrongs,
              {"a": a, "s0": s0}, seed, rng)


@register("fourier")
def gen_fourier(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    n = int(rng.integers(1, 6))
    ell = int(rng.integers(1, 5))
    if ask == "a_n":
        answer = 4 * ell * ell * (-1) ** n / (n * n * math.pi * math.pi)
        stmt = (
            f"For f(x) = x² on [−{ell}, {ell}], the Fourier cosine coefficients are "
            f"aₙ = 4L²(−1)ⁿ/(n²π²). Find a_{n} with L = {ell}. Round to 3 decimals."
        )
        wrongs = [2 * ell * ell / (n * math.pi), -answer,
                  4 * ell / (n * n * math.pi * math.pi)]
        return _p("fourier", "a_n", stmt, answer, wrongs,
                  {"n": n, "ell": ell}, seed, rng)
    answer = 2 * ell / (n * math.pi) * (-1) ** (n + 1)
    stmt = (
        f"For f(x) = x on [−{ell}, {ell}], the Fourier sine coefficients are "
        f"bₙ = (2L/(nπ))(−1)ⁿ⁺¹. Find b_{n} with L = {ell}. Round to 3 decimals."
    )
    wrongs = [-answer, 2 * ell / (n * math.pi), ell / (n * math.pi)]
    return _p("fourier", "b_n", stmt, answer, wrongs,
              {"n": n, "ell": ell}, seed, rng)


@register("bvp_eigenvalue")
def gen_bvp_eigenvalue(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    n = int(rng.integers(1, 6))
    ell = int(rng.integers(1, 6))
    answer = (n * math.pi / ell) ** 2
    stmt = (
        f"The boundary-value problem X'' + λX = 0, X(0) = X({ell}) = 0 has "
        f"eigenvalues λₙ = (nπ/L)². Find λ_{n} with L = {ell}. Round to 3 decimals."
    )
    wrongs = [n * math.pi / ell, (n * math.pi / ell), (math.pi / ell) ** 2]
    return _p("bvp_eigenvalue", "lambda_n", stmt, answer, wrongs,
              {"n": n, "ell": ell}, seed, rng)


@register("heat_mode")
def gen_heat_mode(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    ell = int(rng.integers(2, 6))
    bcoef = int(rng.integers(2, 9))
    alpha = round(float(rng.uniform(0.1, 1.0)), 2)
    x = round(float(rng.uniform(0.5, ell - 0.5)), 2)
    t = round(float(rng.uniform(0.1, 1.5)), 2)
    answer = bcoef * math.sin(math.pi * x / ell) * math.exp(-(math.pi / ell) ** 2 * alpha * t)
    stmt = (
        f"The heat equation u_t = {alpha}·u_xx on [0, {ell}] with "
        f"u(x,0) = {bcoef}·sin(πx/{ell}) has solution "
        f"u(x,t) = {bcoef}·sin(πx/{ell})·e^(−(π/{ell})²·{alpha}·t). "
        f"Find u({x}, {t}). Round to 3 decimals."
    )
    wrongs = [bcoef * math.sin(math.pi * x / ell),
              bcoef * math.exp(-(math.pi / ell) ** 2 * alpha * t),
              bcoef * math.sin(math.pi * x / ell) * math.exp((math.pi / ell) ** 2 * alpha * t)]
    return _p("heat_mode", "value", stmt, answer, wrongs,
              {"ell": ell, "bcoef": bcoef, "alpha": alpha, "x": x, "t": t},
              seed, rng)


@register("wave_mode")
def gen_wave_mode(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    ell = int(rng.integers(2, 6))
    n = int(rng.integers(1, 4))
    bcoef = int(rng.integers(2, 9))
    cspeed = int(rng.integers(1, 4))
    x = round(float(rng.uniform(0.5, ell - 0.5)), 2)
    t = round(float(rng.uniform(0.1, 1.5)), 2)
    answer = (bcoef * math.sin(n * math.pi * x / ell)
              * math.cos(n * math.pi * cspeed * t / ell))
    stmt = (
        f"A vibrating string u_tt = {cspeed}²·u_xx on [0, {ell}] in mode {n} has "
        f"u(x,t) = {bcoef}·sin({n}πx/{ell})·cos({n}π·{cspeed}·t/{ell}). "
        f"Find u({x}, {t}). Round to 3 decimals."
    )
    wrongs = [bcoef * math.sin(n * math.pi * x / ell),
              bcoef * math.cos(n * math.pi * cspeed * t / ell),
              -answer]
    return _p("wave_mode", "value", stmt, answer, wrongs,
              {"ell": ell, "n": n, "bcoef": bcoef, "cspeed": cspeed,
               "x": x, "t": t}, seed, rng)
