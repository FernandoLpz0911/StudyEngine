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


_KINDS = [
    "separable_growth", "first_order_linear", "second_order_homog",
    "laplace_transform", "newton_cooling", "integrating_factor", "euler_method",
    "laplace_inverse", "exact_equation", "newtonian", "mixing", "population",
    "mass_spring", "char_complex", "wronskian", "undetermined", "cauchy_euler",
    "vibrations", "rlc", "rk4_step", "system_eig", "laplace_props", "laplace_ivp",
    "step_function", "dirac_delta", "fourier", "bvp_eigenvalue", "heat_mode",
    "wave_mode",
]


def worked_steps(kind: str, ask: str, params: dict) -> list[str]:
    """Adapter so the central solver registry can reach the diffeq solutions."""
    return solve(kind, ask, params).steps


for _kind in _KINDS:
    register_solver(_kind)(worked_steps)


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
        "exact_equation": lambda: _exact(ask, params),
        "newtonian": lambda: _newtonian(ask, params),
        "mixing": lambda: _mixing(params),
        "population": lambda: _population(ask, params),
        "mass_spring": lambda: _mass_spring(ask, params),
        "char_complex": lambda: _char_complex(ask, params),
        "wronskian": lambda: _wronskian(params),
        "undetermined": lambda: _undetermined(ask, params),
        "cauchy_euler": lambda: _cauchy_euler(ask, params),
        "vibrations": lambda: _vibrations(ask, params),
        "rlc": lambda: _rlc(ask, params),
        "rk4_step": lambda: _rk4(params),
        "system_eig": lambda: _system_eig(ask, params),
        "laplace_props": lambda: _laplace_props(params),
        "laplace_ivp": lambda: _laplace_ivp(params),
        "step_function": lambda: _step(params),
        "dirac_delta": lambda: _dirac(ask, params),
        "fourier": lambda: _fourier(ask, params),
        "bvp_eigenvalue": lambda: _bvp(params),
        "heat_mode": lambda: _heat(params),
        "wave_mode": lambda: _wave(params),
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


def _S(ans, *steps):
    return Solved(list(steps), round(ans, 3))


def _exact(ask, p):
    if ask == "potential_value":
        a, b, c, x0, y0 = p["a"], p["b"], p["c"], p["x0"], p["y0"]
        ans = a * x0 * y0 + b * x0 * x0 + c * y0 * y0
        return _S(ans, "Exact ⇒ solutions are level curves F(x,y) = C.",
                  f"F({x0},{y0}) = {a}·{x0}·{y0} + {b}·{x0}² + {c}·{y0}² "
                  f"= {round(ans, 3)}.")
    a, aa = p["a"], p["aa"]
    ans = 1.0 if a == aa else 0.0
    return _S(ans, "Exact ⇔ ∂M/∂y = ∂N/∂x.",
              f"∂M/∂y = {a}, ∂N/∂x = {aa} ⇒ {'exact (1)' if a == aa else 'not exact (0)'}.")


def _newtonian(ask, p):
    m, b = p["m"], p["bdrag"]
    term = m * 9.8 / b
    if ask == "velocity_t":
        t1 = p["t1"]
        ans = term * (1 - math.exp(-b / m * t1))
        return _S(ans, f"v(t) = (mg/b)(1 − e^(−bt/m)), terminal mg/b = {round(term, 3)}.",
                  f"v({t1}) = {round(ans, 3)}.")
    return _S(term, "As t → ∞ the drag balances gravity: v_term = mg/b.",
              f"= {m}·9.8/{b} = {round(term, 3)}.")


def _mixing(p):
    vol, cin, r, a0, t1 = p["vol"], p["cin"], p["r"], p["a0"], p["t1"]
    eq = vol * cin
    ans = eq + (a0 - eq) * math.exp(-(r / vol) * t1)
    return _S(ans, f"A(t) = V·c + (A₀ − V·c)·e^(−(r/V)t); equilibrium V·c = {eq}.",
              f"A({t1}) = {round(ans, 3)}.")


def _population(ask, p):
    p0, r, t1 = p["p0"], p["r"], p["t1"]
    if ask == "logistic":
        k = p["k"]
        ans = k / (1 + (k - p0) / p0 * math.exp(-r * t1))
        return _S(ans, "Logistic: P(t) = K / (1 + ((K−P₀)/P₀)·e^(−rt)).",
                  f"P({t1}) = {round(ans, 3)} (carrying capacity {k:.0f}).")
    ans = p0 * math.exp(r * t1)
    return _S(ans, "Exponential: P(t) = P₀·e^(rt).",
              f"P({t1}) = {p0}·e^({r}·{t1}) = {round(ans, 3)}.")


def _mass_spring(ask, p):
    m, k = p["m"], p["k"]
    omega = math.sqrt(k / m)
    if ask == "period":
        ans = 2 * math.pi / omega
        return _S(ans, f"ω = √(k/m) = {round(omega, 3)}; period = 2π/ω.",
                  f"= {round(ans, 3)}.")
    if ask == "damped_freq":
        c = p["c"]
        ans = math.sqrt(k / m - (c / (2 * m)) ** 2)
        return _S(ans, "ω_d = √(k/m − (c/2m)²).", f"= {round(ans, 3)}.")
    return _S(omega, "Natural frequency ω = √(k/m).",
              f"= √({k}/{m}) = {round(omega, 3)}.")


def _char_complex(ask, p):
    alpha, beta = p["alpha"], p["beta"]
    if ask == "imag_part":
        return _S(float(beta), "Roots α ± βi with β = √(4q − p²)/2.",
                  f"β = {beta}.")
    return _S(float(alpha), "Roots α ± βi with α = −p/2.", f"α = {alpha}.")


def _wronskian(p):
    r1, r2, t0 = p["r1"], p["r2"], p["t0"]
    ans = (r2 - r1) * math.exp((r1 + r2) * t0)
    return _S(ans, "W = (r₂ − r₁)·e^((r₁+r₂)t) for y = e^(rt) solutions.",
              f"W({t0}) = {round(ans, 3)} ≠ 0 ⇒ independent.")


def _undetermined(ask, p):
    if ask == "trig_amp":
        q, w, f0 = p["q"], p["w"], p["f0"]
        ans = f0 / (q - w * w)
        return _S(ans, "y_p = A·cos(ωt), A = F₀/(q − ω²).", f"A = {round(ans, 3)}.")
    if ask == "poly_const":
        q, c = p["q"], p["c"]
        ans = c / q
        return _S(ans, "Constant forcing ⇒ y_p = C/q.", f"= {round(ans, 3)}.")
    pp, q, r, amp = p["p"], p["q"], p["r"], p["amp"]
    ans = amp / (r * r + pp * r + q)
    return _S(ans, "y_p = A·e^(rt), A = F₀/(r² + p·r + q).", f"A = {round(ans, 3)}.")


def _cauchy_euler(ask, p):
    r1, r2 = p["r1"], p["r2"]
    ans = float(r1 if ask == "smaller_root" else r2)
    return _S(ans, "Try y = x^r ⇒ r(r−1) + b·r + c = 0.",
              f"Roots {r1}, {r2}; the {'smaller' if ask == 'smaller_root' else 'larger'} is {ans}.")


def _vibrations(ask, p):
    m, k = p["m"], p["k"]
    if ask == "steady_amplitude":
        c, w, f0 = p["c"], p["w"], p["f0"]
        ans = f0 / math.sqrt((k - m * w * w) ** 2 + (c * w) ** 2)
        return _S(ans, "Amplitude = F₀/√((k − mω²)² + (cω)²).", f"= {round(ans, 3)}.")
    c = p["c"]
    ans = math.sqrt(k / m - (c / (2 * m)) ** 2)
    return _S(ans, "Damped frequency ω_d = √(k/m − (c/2m)²).", f"= {round(ans, 3)}.")


def _rlc(ask, p):
    ind, cap = p["ind"], p["cap"]
    if ask == "damped_freq":
        res = p["res"]
        ans = math.sqrt(1 / (ind * cap) - (res / (2 * ind)) ** 2)
        return _S(ans, "ω_d = √(1/(LC) − (R/2L)²).", f"= {round(ans, 3)}.")
    ans = 1 / math.sqrt(ind * cap)
    return _S(ans, "Natural frequency ω₀ = 1/√(LC).", f"= {round(ans, 3)}.")


def _rk4(p):
    lam, y0, h = p["lam"], p["y0"], p["h"]
    k1 = lam * y0
    k2 = lam * (y0 + h * k1 / 2)
    k3 = lam * (y0 + h * k2 / 2)
    k4 = lam * (y0 + h * k3)
    ans = y0 + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    return _S(ans, "RK4: y₁ = y₀ + h/6·(k₁ + 2k₂ + 2k₃ + k₄).",
              f"= {round(ans, 3)}.")


def _system_eig(ask, p):
    a, b, c, d = p["a"], p["b"], p["c"], p["d"]
    tr, det = a + d, a * d - b * c
    root = math.sqrt(tr * tr - 4 * det)
    ans = (tr + root) / 2 if ask != "smaller_eig" else (tr - root) / 2
    return _S(ans, f"trace = {tr}, det = {det}; λ = (tr ± √(tr²−4det))/2.",
              f"= {round(ans, 3)}.")


def _laplace_props(p):
    a, w, s0 = p["a"], p["w"], p["s0"]
    ans = (s0 - a) / ((s0 - a) ** 2 + w * w)
    return _S(ans, "Shift: L{e^(at)cos(ωt)} = (s−a)/((s−a)² + ω²).",
              f"At s = {s0}: {round(ans, 3)}.")


def _laplace_ivp(p):
    a, y0, t1 = p["a"], p["y0"], p["t1"]
    ans = y0 * math.exp(-a * t1)
    return _S(ans, f"Y = {y0}/(s + {a}) ⇒ y(t) = {y0}·e^(−{a}t).",
              f"y({t1}) = {round(ans, 3)}.")


def _step(p):
    a, s0 = p["a"], p["s0"]
    ans = math.exp(-a * s0) / s0
    return _S(ans, "L{u(t−a)} = e^(−as)/s.",
              f"At s = {s0}: e^(−{a}·{s0})/{s0} = {round(ans, 3)}.")


def _dirac(ask, p):
    if ask == "impulse_response":
        coef, t1 = p["coef"], p["t1"]
        ans = math.exp(-coef * t1)
        return _S(ans, f"y' + {coef}y = δ(t) ⇒ y = e^(−{coef}t).",
                  f"y({t1}) = {round(ans, 3)}.")
    a, s0 = p["a"], p["s0"]
    ans = math.exp(-a * s0)
    return _S(ans, "L{δ(t−a)} = e^(−as).",
              f"At s = {s0}: e^(−{a}·{s0}) = {round(ans, 3)}.")


def _fourier(ask, p):
    n, ell = p["n"], p["ell"]
    if ask == "a_n":
        ans = 4 * ell * ell * (-1) ** n / (n * n * math.pi * math.pi)
        return _S(ans, "f = x²: aₙ = 4L²(−1)ⁿ/(n²π²).", f"a_{n} = {round(ans, 3)}.")
    ans = 2 * ell / (n * math.pi) * (-1) ** (n + 1)
    return _S(ans, "f = x: bₙ = (2L/nπ)(−1)ⁿ⁺¹.", f"b_{n} = {round(ans, 3)}.")


def _bvp(p):
    n, ell = p["n"], p["ell"]
    ans = (n * math.pi / ell) ** 2
    return _S(ans, "X'' + λX = 0, X(0)=X(L)=0 ⇒ λₙ = (nπ/L)².",
              f"λ_{n} = {round(ans, 3)}.")


def _heat(p):
    ell, b, al, x, t = p["ell"], p["bcoef"], p["alpha"], p["x"], p["t"]
    ans = b * math.sin(math.pi * x / ell) * math.exp(-(math.pi / ell) ** 2 * al * t)
    return _S(ans, "Single mode: u = B·sin(πx/L)·e^(−(π/L)²αt).",
              f"u({x},{t}) = {round(ans, 3)}.")


def _wave(p):
    ell, n, b, cs, x, t = p["ell"], p["n"], p["bcoef"], p["cspeed"], p["x"], p["t"]
    ans = b * math.sin(n * math.pi * x / ell) * math.cos(n * math.pi * cs * t / ell)
    return _S(ans, "Standing wave: u = B·sin(nπx/L)·cos(nπct/L).",
              f"u({x},{t}) = {round(ans, 3)}.")
