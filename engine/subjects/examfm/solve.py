"""Worked solutions for Exam FM problems (same closed forms as the generators)."""
from __future__ import annotations

from math import exp, log

from engine.feedback.solve import register_solver
from engine.subjects.examfm.generators import _afv, _apv, _irr


def _r(x: float) -> float:
    return round(x, 4)


@register_solver("fm_compound")
def solve_compound(kind: str, ask: str, p: dict) -> list[str]:
    i = p.get("i")
    if ask == "future_value":
        return ["FV = PV·(1+i)^n.",
                f"= {p['pv']}·(1+{i})^{p['n']} = {_r(p['pv'] * (1 + i) ** p['n'])}."]
    if ask == "present_value":
        return ["PV = FV·(1+i)^(−n).",
                f"= {p['fv']}·(1+{i})^(−{p['n']}) = {_r(p['fv'] * (1 + i) ** -p['n'])}."]
    if ask == "simple_interest":
        return ["Simple interest: A = P·(1 + i·n).",
                f"= {p['p']}·(1+{i}·{p['n']}) = {_r(p['p'] * (1 + i * p['n']))}."]
    if ask == "discount_factor":
        return ["Discount factor v = 1/(1+i).", f"= {_r(1 / (1 + i))}."]
    if ask == "effective_discount":
        return ["d = i/(1+i).", f"= {i}/(1+{i}) = {_r(i / (1 + i))}."]
    if ask == "nominal_discount":
        m = p["m"]
        return [f"d^({m}) = m·(1 − (1+i)^(−1/m)).",
                f"= {_r(m * (1 - (1 + i) ** (-1 / m)))}."]
    if ask == "force_from_i":
        return ["Force of interest δ = ln(1+i).", f"= {_r(log(1 + i))}."]
    if ask == "real_rate":
        r = p["infl"]
        return ["Real rate = (1+i)/(1+r) − 1.", f"= {_r((1 + i) / (1 + r) - 1)}."]
    nominal, m = p["nominal"], p["m"]
    return ["Effective rate i = (1 + i^(m)/m)^m − 1.",
            f"= {_r(((1 + nominal / m) ** m - 1) * 100)}%."]


@register_solver("fm_varforce")
def solve_varforce(kind: str, ask: str, p: dict) -> list[str]:
    if ask == "accum_const":
        return ["Constant force: AV = P·e^(δ·t).",
                f"= {p['p']}·e^({p['delta']}·{p['t']}) "
                f"= {_r(p['p'] * exp(p['delta'] * p['t']))}."]
    a, b, t, pp = p["a"], p["b"], p["t"], p["p"]
    return ["∫₀ᵗ (a+bs) ds = a·t + b·t²/2, so AV = P·exp(a·t + b·t²/2).",
            f"= {pp}·exp({a}·{t} + {b}·{t}²/2) "
            f"= {_r(pp * exp(a * t + b * t * t / 2))}."]


@register_solver("fm_annuity")
def solve_annuity(kind: str, ask: str, p: dict) -> list[str]:
    i = p["i"]
    pmt = p.get("pmt")
    n = p.get("n")
    if ask == "annuity_pv":
        return ["PV = PMT·a_n = PMT·(1−vⁿ)/i.", f"= {_r(pmt * _apv(i, n))}."]
    if ask == "annuity_fv":
        return ["FV = PMT·s_n = PMT·((1+i)ⁿ−1)/i.", f"= {_r(pmt * _afv(i, n))}."]
    if ask == "annuity_due_pv":
        return ["PV = PMT·a_n·(1+i).", f"= {_r(pmt * _apv(i, n) * (1 + i))}."]
    if ask == "annuity_due_fv":
        return ["FV = PMT·s_n·(1+i).", f"= {_r(pmt * _afv(i, n) * (1 + i))}."]
    if ask == "perpetuity":
        return ["Perpetuity-immediate: PV = PMT/i.", f"= {_r(pmt / i)}."]
    if ask == "perpetuity_due":
        return ["Perpetuity-due: PV = PMT·(1+i)/i.", f"= {_r(pmt * (1 + i) / i)}."]
    if ask == "deferred":
        k = p["k"]
        ans = pmt * _apv(i, n) * (1 + i) ** -k
        return ["Deferred: PV = vᵏ·PMT·a_n.", f"= {_r(ans)}."]
    if ask == "mthly":
        m = p["m"]
        im = m * ((1 + i) ** (1 / m) - 1)
        return [f"PV = PMT·(1−vⁿ)/i^({m}), with i^({m}) = {_r(im)}.",
                f"= {_r(pmt * (1 - (1 + i) ** -n) / im)}."]
    if ask == "continuous":
        delta = log(1 + i)
        return ["Continuous: PV = PMT·(1−vⁿ)/δ, δ = ln(1+i).",
                f"= {_r(pmt * (1 - (1 + i) ** -n) / delta)}."]
    if ask == "increasing":
        adue = _apv(i, n) * (1 + i)
        return ["(Ia)_n = (ä_n − n·vⁿ)/i.",
                f"= {_r(pmt * (adue - n * (1 + i) ** -n) / i)}."]
    if ask == "decreasing":
        return ["(Da)_n = (n − a_n)/i.",
                f"= {_r(pmt * (n - _apv(i, n)) / i)}."]
    if ask == "geometric":
        g = p["g"]
        ratio = (1 + g) / (1 + i)
        return ["Geometric: PV = PMT·(1 − ((1+g)/(1+i))ⁿ)/(i−g).",
                f"= {_r(pmt * (1 - ratio ** n) / (i - g))}."]
    if ask == "solve_term":
        loan = p["loan"]
        return ["Solve L = PMT·a_n for n: n = −ln(1 − L·i/PMT)/ln(1+i).",
                f"= {_r(-log(1 - loan * i / p['pmt']) / log(1 + i))}."]
    loan = p["loan"]
    return ["Level payment: PMT = L·i/(1 − vⁿ).",
            f"= {_r(loan * i / (1 - (1 + i) ** -n))}."]


@register_solver("fm_loan")
def solve_loan(kind: str, ask: str, p: dict) -> list[str]:
    i, n, loan = p["i"], p["n"], p["loan"]
    pmt = loan * i / (1 - (1 + i) ** -n)
    k = p.get("k")
    if ask == "balance_prospective":
        return ["Prospective balance = PMT·a_(n−k).",
                f"= {_r(pmt * _apv(i, n - k))}."]
    if ask == "balance_retrospective":
        return ["Retrospective balance = L·(1+i)^k − PMT·s_k.",
                f"= {_r(loan * (1 + i) ** k - pmt * _afv(i, k))}."]
    if ask == "interest_portion":
        return ["Interest in payment k = PMT·(1 − v^(n−k+1)).",
                f"= {_r(pmt * (1 - (1 + i) ** -(n - k + 1)))}."]
    if ask == "principal_portion":
        return ["Principal in payment k = PMT·v^(n−k+1).",
                f"= {_r(pmt * (1 + i) ** -(n - k + 1))}."]
    if ask == "balloon":
        r = p["r"]
        bal = loan * (1 + i) ** (n - 1) - r * _afv(i, n - 1)
        return ["Balance after n−1 payments of R, then settle with interest.",
                f"final = [L(1+i)^(n−1) − R·s_(n−1)]·(1+i) = {_r(bal * (1 + i))}."]
    j = p["j"]
    dep = loan / _afv(j, n)
    return ["Sinking fund: outlay = L·i (interest) + L/s_n‖j (fund deposit).",
            f"= {loan}·{i} + {_r(dep)} = {_r(loan * i + dep)}."]


@register_solver("fm_bond")
def solve_bond(kind: str, ask: str, p: dict) -> list[str]:
    face, r = p["face"], p["r"]
    coupon = face * r
    if ask == "accumulated_reinvest":
        j, n = p["j"], p["n"]
        return ["Reinvest coupons at j, add redemption: Fr·s_n‖j + C.",
                f"= {_r(coupon * _afv(j, n) + face)}."]
    if ask == "callable_price":
        i, n1, n2 = p["i"], p["n1"], p["n2"]
        p1 = coupon * _apv(i, n1) + face * (1 + i) ** -n1
        p2 = coupon * _apv(i, n2) + face * (1 + i) ** -n2
        return [f"Price at each call date: year {n1} → {_r(p1)}, "
                f"year {n2} → {_r(p2)}.",
                f"Use the minimum to guarantee the yield: {_r(min(p1, p2))}."]
    i, n = p["i"], p["n"]
    price = coupon * _apv(i, n) + face * (1 + i) ** -n
    if ask == "premium_discount":
        return ["Premium = price − redemption (negative ⇒ discount).",
                f"= {_r(price)} − {face} = {_r(price - face)}."]
    if ask == "book_value":
        t = p["t"]
        return ["Book value = Fr·a_(n−t) + C·v^(n−t).",
                f"= {_r(coupon * _apv(i, n - t) + face * (1 + i) ** -(n - t))}."]
    if ask == "amort_premium":
        t = p["t"]
        bv = coupon * _apv(i, n - t + 1) + face * (1 + i) ** -(n - t + 1)
        return ["Premium amortized = coupon − yield·(prior book value).",
                f"= {coupon} − {i}·{_r(bv)} = {_r(coupon - i * bv)}."]
    return ["Price = coupon·a_n + redemption·vⁿ.", f"= {_r(price)}."]


@register_solver("fm_yield")
def solve_yield(kind: str, ask: str, p: dict) -> list[str]:
    if ask == "dollar_weighted":
        a, dep, b = p["a"], p["dep"], p["b"]
        return ["Dollar-weighted ≈ I / (A + Σ deposit·(1−t)), I = B−A−deposits.",
                f"= ({b}−{a}−{dep}) / ({a}+0.5·{dep}) "
                f"= {_r((b - a - dep) / (a + 0.5 * dep))}."]
    if ask == "time_weighted":
        a, mid, dep, b = p["a"], p["mid"], p["dep"], p["b"]
        return ["Time-weighted = ∏(sub-period growth) − 1.",
                f"= ({mid}/{a})·({b}/({mid}+{dep})) − 1 "
                f"= {_r((mid / a) * (b / (mid + dep)) - 1)}."]
    cfs = p["cfs"]
    return ["IRR solves NPV = Σ CFₜ·(1+i)^(−t) = 0 (here by iteration).",
            f"i = {_r(_irr(cfs))}."]


@register_solver("fm_termstructure")
def solve_termstructure(kind: str, ask: str, p: dict) -> list[str]:
    if ask == "pv_spot":
        spots, cfs = p["spots"], p["cfs"]
        pv = sum(c / (1 + s) ** (t + 1)
                 for t, (c, s) in enumerate(zip(cfs, spots, strict=True)))
        return ["Discount each cash flow at its own spot rate: Σ CFₜ/(1+sₜ)ᵗ.",
                f"= {_r(pv)}."]
    s1, s2 = p["s1"], p["s2"]
    return ["Forward rate: f = (1+s₂)²/(1+s₁) − 1.",
            f"= (1+{s2})²/(1+{s1}) − 1 = {_r((1 + s2) ** 2 / (1 + s1) - 1)}."]


@register_solver("fm_duration")
def solve_duration(kind: str, ask: str, p: dict) -> list[str]:
    i, cfs = p["i"], p["cfs"]
    times = [1, 2, 3, 4]
    v = 1 / (1 + i)
    pv = [c * v ** t for c, t in zip(cfs, times, strict=True)]
    price = sum(pv)
    mac = sum(t * x for t, x in zip(times, pv, strict=True)) / price
    if ask == "modified":
        return ["Modified duration = Macaulay / (1+i).",
                f"Macaulay = {_r(mac)}, so ModDur = {_r(mac / (1 + i))}."]
    if ask == "convexity":
        conv = sum(t * (t + 1) * c * v ** (t + 2)
                   for c, t in zip(cfs, times, strict=True)) / price
        return ["Convexity = Σ t(t+1)·CFₜ·v^(t+2) / P.", f"= {_r(conv)}."]
    if ask == "pv_change":
        di = p["di"]
        moddur = mac / (1 + i)
        return ["First-order: ΔP ≈ −P·ModDur·Δi.",
                f"= −{_r(price)}·{_r(moddur)}·{di} "
                f"= {_r(-price * moddur * di)}."]
    return ["Macaulay duration = Σ t·PVₜ / Σ PVₜ.",
            f"= {_r(mac)} (price P = {_r(price)})."]
