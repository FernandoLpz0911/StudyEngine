"""Exam FM (Financial Mathematics) generators — closed-form drills.

Every Exam FM outcome that is a single number (accumulated/present values, annuity
and loan figures, bond prices and book values, durations, yields) is an exact
function of its inputs, so each answer and its worked solution share one
computation. Yields/IRR with no closed form use a deterministic bisection.
"""
from __future__ import annotations

from math import exp, log

import numpy as np

from engine.generation.base import Problem, make_mc_choices, register

COMPOUND = ["future_value", "present_value", "effective_rate", "simple_interest",
            "discount_factor", "effective_discount", "nominal_discount",
            "force_from_i", "real_rate"]
ANNUITY = ["annuity_pv", "annuity_fv", "perpetuity", "loan_payment",
           "annuity_due_pv", "annuity_due_fv", "perpetuity_due", "deferred",
           "mthly", "continuous", "increasing", "decreasing", "geometric",
           "solve_term"]
VARFORCE = ["accum", "accum_const"]
LOAN = ["balance_prospective", "balance_retrospective", "interest_portion",
        "principal_portion", "balloon", "sinking_fund"]
BOND = ["price", "premium_discount", "book_value", "amort_premium",
        "accumulated_reinvest", "callable_price"]
YIELD = ["irr", "dollar_weighted", "time_weighted"]
TERM = ["forward", "pv_spot"]
DURATION = ["macaulay", "modified", "convexity", "pv_change"]


def _apv(i: float, n: float) -> float:
    """Annuity-immediate present-value factor a_n|i."""
    return (1 - (1 + i) ** -n) / i


def _afv(i: float, n: float) -> float:
    """Annuity-immediate accumulated-value factor s_n|i."""
    return ((1 + i) ** n - 1) / i


def _irr(cfs: list[float]) -> float:
    """Bisection for the rate with NPV(cfs) = 0 (cfs[t] at time t)."""
    def npv(r: float) -> float:
        return sum(c * (1 + r) ** (-t) for t, c in enumerate(cfs))

    lo, hi = 1e-6, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _result(kind, family, statement, answer, wrongs, extra, seed, rng):
    return Problem(kind, family, statement, round(answer, 3),
                   make_mc_choices(answer, wrongs, rng), params=extra, seed=seed)


@register("fm_compound")
def gen_fm_compound(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    family = ask if ask in COMPOUND else str(rng.choice(COMPOUND))
    i = round(float(rng.uniform(0.02, 0.10)), 3)
    n = int(rng.integers(2, 16))

    if family == "future_value":
        pv = round(float(rng.uniform(500, 5000)), 2)
        answer = pv * (1 + i) ** n
        wrongs = [pv * (1 + i * n), pv * (1 - i) ** n, pv * (1 + i) ** -n]
        statement = (
            f"You invest ${pv} at an annual effective rate of {i}. What is its "
            f"accumulated value after {n} years? Round to 2 decimals."
        )
        extra = {"pv": pv, "i": i, "n": n}
    elif family == "present_value":
        fv = round(float(rng.uniform(1000, 8000)), 2)
        answer = fv * (1 + i) ** -n
        wrongs = [fv * (1 + i) ** n, fv / (1 + i * n), fv * (1 - i) ** n]
        statement = (
            f"A payment of ${fv} is due in {n} years. At an annual effective rate "
            f"of {i}, what is its present value? Round to 2 decimals."
        )
        extra = {"fv": fv, "i": i, "n": n}
    elif family == "simple_interest":
        p = round(float(rng.uniform(500, 5000)), 2)
        answer = p * (1 + i * n)
        wrongs = [p * (1 + i) ** n, p * (1 + i), p * i * n]
        statement = (
            f"${p} is invested at a simple interest rate of {i} per year. What is "
            f"its accumulated value after {n} years? Round to 2 decimals."
        )
        extra = {"p": p, "i": i, "n": n, "simple": 1}
    elif family == "discount_factor":
        answer = 1 / (1 + i)
        wrongs = [1 - i, 1 / (1 - i), i / (1 + i)]
        statement = (
            f"The annual effective interest rate is {i}. What is the one-year "
            f"discount factor v = 1/(1+i)? Round to 3 decimals."
        )
        extra = {"i": i}
    elif family == "effective_discount":
        answer = i / (1 + i)
        wrongs = [i, i * (1 + i), 1 / (1 + i)]
        statement = (
            f"The annual effective interest rate is {i}. What is the annual "
            f"effective discount rate d = i/(1+i)? Round to 3 decimals."
        )
        extra = {"i": i}
    elif family == "nominal_discount":
        m = int(rng.choice([2, 4, 12]))
        answer = m * (1 - (1 + i) ** (-1 / m))
        wrongs = [i / (1 + i), m * ((1 + i) ** (1 / m) - 1), i]
        statement = (
            f"The annual effective interest rate is {i}. Find the nominal discount "
            f"rate d^({m}) convertible {m}-thly. Round to 4 decimals."
        )
        extra = {"i": i, "m": m}
    elif family == "force_from_i":
        answer = log(1 + i)
        wrongs = [i, i / (1 + i), exp(i) - 1]
        statement = (
            f"The annual effective interest rate is {i}. What is the (constant) "
            f"force of interest δ = ln(1+i)? Round to 4 decimals."
        )
        extra = {"i": i}
    elif family == "real_rate":
        infl = round(float(rng.uniform(0.01, 0.05)), 3)
        answer = (1 + i) / (1 + infl) - 1
        wrongs = [i - infl, i + infl, (1 + i) * (1 + infl) - 1]
        statement = (
            f"The annual effective rate is {i} and inflation is {infl}. What is "
            f"the real rate of interest (1+i)/(1+r)−1? Round to 4 decimals."
        )
        extra = {"i": i, "infl": infl}
    else:
        nominal = round(float(rng.uniform(0.04, 0.12)), 3)
        m = int(rng.choice([2, 4, 12]))
        answer = ((1 + nominal / m) ** m - 1) * 100
        wrongs = [nominal * 100, ((1 + nominal) ** m - 1) * 100, nominal / m * 100]
        statement = (
            f"A nominal annual rate of {nominal} is compounded {m} times per year. "
            f"What is the annual effective rate, as a percentage? Round to 2 decimals."
        )
        family = "effective_rate"
        extra = {"nominal": nominal, "m": m}

    return _result("fm_compound", family, statement, answer, wrongs, extra, seed, rng)


@register("fm_varforce")
def gen_fm_varforce(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    family = ask if ask in VARFORCE else str(rng.choice(VARFORCE))
    p = round(float(rng.uniform(500, 5000)), 2)
    t = int(rng.integers(3, 11))

    if family == "accum_const":
        delta = round(float(rng.uniform(0.03, 0.08)), 3)
        answer = p * exp(delta * t)
        wrongs = [p * (1 + delta) ** t, p * exp(delta), p * (1 + delta * t)]
        statement = (
            f"Under a constant force of interest δ = {delta}, ${p} is invested. "
            f"What is its accumulated value after {t} years? Round to 2 decimals."
        )
        extra = {"p": p, "delta": delta, "t": t}
    else:
        a = round(float(rng.uniform(0.02, 0.05)), 3)
        b = round(float(rng.uniform(0.004, 0.015)), 3)
        factor = exp(a * t + b * t * t / 2)
        answer = p * factor
        wrongs = [p * exp(a * t), p * exp((a + b * t) * t), p * (1 + a * t)]
        statement = (
            f"The force of interest is δ(t) = {a} + {b}·t. ${p} is invested at "
            f"time 0. Find its accumulated value at time {t} "
            f"(factor = exp(∫₀^{t} δ(s) ds)). Round to 2 decimals."
        )
        extra = {"p": p, "a": a, "b": b, "t": t}

    return _result("fm_varforce", family, statement, answer, wrongs, extra, seed, rng)


@register("fm_annuity")
def gen_fm_annuity(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    family = ask if ask in ANNUITY else str(rng.choice(ANNUITY))
    i = round(float(rng.uniform(0.03, 0.10)), 3)
    n = int(rng.integers(3, 21))
    pmt = round(float(rng.uniform(100, 1000)), 2)

    if family == "annuity_pv":
        answer = pmt * _apv(i, n)
        wrongs = [pmt * (1 - (1 + i) ** -n), pmt * n, pmt / i]
        statement = (
            f"An annuity-immediate pays ${pmt} at the end of each year for {n} "
            f"years at annual effective rate {i}. Find its present value. "
            f"Round to 2 decimals."
        )
        extra = {"pmt": pmt, "i": i, "n": n}
    elif family == "annuity_fv":
        answer = pmt * _afv(i, n)
        wrongs = [pmt * ((1 + i) ** n - 1), pmt * n, pmt * (1 + i) ** n]
        statement = (
            f"An annuity-immediate pays ${pmt} at the end of each year for {n} "
            f"years at annual effective rate {i}. Find its accumulated value. "
            f"Round to 2 decimals."
        )
        extra = {"pmt": pmt, "i": i, "n": n}
    elif family == "annuity_due_pv":
        answer = pmt * _apv(i, n) * (1 + i)
        wrongs = [pmt * _apv(i, n), pmt * _afv(i, n) * (1 + i), pmt * n]
        statement = (
            f"An annuity-due pays ${pmt} at the START of each year for {n} years "
            f"at annual effective rate {i}. Find its present value. "
            f"Round to 2 decimals."
        )
        extra = {"pmt": pmt, "i": i, "n": n}
    elif family == "annuity_due_fv":
        answer = pmt * _afv(i, n) * (1 + i)
        wrongs = [pmt * _afv(i, n), pmt * _apv(i, n) * (1 + i), pmt * n]
        statement = (
            f"An annuity-due pays ${pmt} at the START of each year for {n} years "
            f"at annual effective rate {i}. Find its accumulated value. "
            f"Round to 2 decimals."
        )
        extra = {"pmt": pmt, "i": i, "n": n}
    elif family == "perpetuity":
        answer = pmt / i
        wrongs = [pmt * i, pmt / (1 + i), pmt * (1 + i) / i]
        statement = (
            f"A perpetuity-immediate pays ${pmt} at the end of each year forever "
            f"at annual effective rate {i}. Find its present value. "
            f"Round to 2 decimals."
        )
        extra = {"pmt": pmt, "i": i}
    elif family == "perpetuity_due":
        answer = pmt * (1 + i) / i
        wrongs = [pmt / i, pmt / (1 - i), pmt * i]
        statement = (
            f"A perpetuity-due pays ${pmt} at the START of each year forever at "
            f"annual effective rate {i}. Find its present value. Round to 2 decimals."
        )
        extra = {"pmt": pmt, "i": i}
    elif family == "deferred":
        k = int(rng.integers(2, 8))
        answer = pmt * _apv(i, n) * (1 + i) ** -k
        wrongs = [pmt * _apv(i, n), pmt * _apv(i, n + k), pmt * _apv(i, n) * (1 + i) ** k]
        statement = (
            f"An annuity-immediate of ${pmt}/year for {n} years is deferred {k} "
            f"years (first payment at time {k + 1}) at rate {i}. Find its present "
            f"value today. Round to 2 decimals."
        )
        extra = {"pmt": pmt, "i": i, "n": n, "k": k}
    elif family == "mthly":
        m = int(rng.choice([2, 4, 12]))
        im = m * ((1 + i) ** (1 / m) - 1)
        answer = pmt * (1 - (1 + i) ** -n) / im
        wrongs = [pmt * _apv(i, n), pmt * (1 - (1 + i) ** -n) / i, pmt * n]
        statement = (
            f"An annuity pays ${pmt} per year, payable {m}-thly (in level "
            f"installments), for {n} years at annual effective rate {i}. Find its "
            f"present value (PV = PMT·(1−vⁿ)/i^({m})). Round to 2 decimals."
        )
        extra = {"pmt": pmt, "i": i, "n": n, "m": m}
    elif family == "continuous":
        delta = log(1 + i)
        answer = pmt * (1 - (1 + i) ** -n) / delta
        wrongs = [pmt * _apv(i, n), pmt * (1 - (1 + i) ** -n) / i, pmt * n]
        statement = (
            f"A continuous annuity pays at an annual rate of ${pmt} for {n} years "
            f"at annual effective rate {i}. Find its present value "
            f"(PV = PMT·(1−vⁿ)/δ). Round to 2 decimals."
        )
        extra = {"pmt": pmt, "i": i, "n": n}
    elif family == "increasing":
        adue = _apv(i, n) * (1 + i)
        answer = pmt * (adue - n * (1 + i) ** -n) / i
        wrongs = [pmt * _apv(i, n), pmt * n * (n + 1) / 2, pmt * (n - _apv(i, n)) / i]
        statement = (
            f"An increasing annuity-immediate pays {pmt}, 2·{pmt}, …, {n}·{pmt} at "
            f"the end of years 1..{n} at rate {i}. Find its present value "
            f"(PMT·(Ia)_n). Round to 2 decimals."
        )
        extra = {"pmt": pmt, "i": i, "n": n}
    elif family == "decreasing":
        answer = pmt * (n - _apv(i, n)) / i
        wrongs = [pmt * _apv(i, n), pmt * n * (n + 1) / 2,
                  pmt * (_apv(i, n) * (1 + i) - n * (1 + i) ** -n) / i]
        statement = (
            f"A decreasing annuity-immediate pays {n}·{pmt}, …, 2·{pmt}, {pmt} at "
            f"the end of years 1..{n} at rate {i}. Find its present value "
            f"(PMT·(Da)_n). Round to 2 decimals."
        )
        extra = {"pmt": pmt, "i": i, "n": n}
    elif family == "geometric":
        g = round(float(rng.uniform(0.01, min(0.04, i - 0.005))), 3)
        ratio = (1 + g) / (1 + i)
        answer = pmt * (1 - ratio ** n) / (i - g)
        wrongs = [pmt * _apv(i, n), pmt * (1 - ratio ** n) / (i + g), pmt * n]
        statement = (
            f"An annuity-immediate first pays ${pmt} at the end of year 1, then "
            f"grows {g} per year for {n} payments, at rate {i}. Find its present "
            f"value. Round to 2 decimals."
        )
        extra = {"pmt": pmt, "i": i, "n": n, "g": g}
    elif family == "solve_term":
        loan = round(float(rng.uniform(2000, 8000)), 2)
        pmt = round(loan * i / (1 - (1 + i) ** -int(rng.integers(5, 15))) * 1.1, 2)
        answer = -log(1 - loan * i / pmt) / log(1 + i)
        wrongs = [loan / pmt, loan * i / pmt, loan / (pmt - loan * i)]
        statement = (
            f"A loan of ${loan} at annual effective rate {i} is repaid by level "
            f"payments of ${pmt} at year-end. How many payments (n, possibly "
            f"fractional) are needed? Round to 3 decimals."
        )
        extra = {"loan": loan, "i": i, "pmt": pmt}
    else:
        loan = round(float(rng.uniform(2000, 20000)), 2)
        answer = loan * i / (1 - (1 + i) ** -n)
        wrongs = [loan / n, loan * i, loan * i / (1 - (1 + i) ** n)]
        statement = (
            f"A loan of ${loan} is repaid with level annual payments over {n} "
            f"years at annual effective rate {i}. Find the annual payment. "
            f"Round to 2 decimals."
        )
        family = "loan_payment"
        extra = {"loan": loan, "i": i, "n": n}

    return _result("fm_annuity", family, statement, answer, wrongs, extra, seed, rng)


@register("fm_loan")
def gen_fm_loan(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    family = ask if ask in LOAN else str(rng.choice(LOAN))
    i = round(float(rng.uniform(0.03, 0.09)), 3)
    n = int(rng.integers(6, 21))
    loan = round(float(rng.uniform(5000, 30000)), 2)
    pmt = loan * i / (1 - (1 + i) ** -n)
    k = int(rng.integers(1, n))

    if family == "balance_prospective":
        answer = pmt * _apv(i, n - k)
        wrongs = [pmt * _apv(i, k), loan - pmt * k, pmt * (n - k)]
        statement = (
            f"A ${loan} loan at rate {i} is repaid by {n} level year-end payments. "
            f"Find the outstanding balance just after payment {k} (prospective: "
            f"PMT·a_(n−k)). Round to 2 decimals."
        )
        extra = {"loan": loan, "i": i, "n": n, "k": k}
    elif family == "balance_retrospective":
        answer = loan * (1 + i) ** k - pmt * _afv(i, k)
        wrongs = [pmt * _apv(i, n - k), loan - pmt * k, loan * (1 + i) ** k]
        statement = (
            f"A ${loan} loan at rate {i} is repaid by {n} level year-end payments. "
            f"Find the outstanding balance just after payment {k} (retrospective: "
            f"L(1+i)^k − PMT·s_k). Round to 2 decimals."
        )
        extra = {"loan": loan, "i": i, "n": n, "k": k}
    elif family == "interest_portion":
        answer = pmt * (1 - (1 + i) ** -(n - k + 1))
        wrongs = [pmt * (1 + i) ** -(n - k + 1), pmt * i, i * loan]
        statement = (
            f"A ${loan} loan at rate {i} is repaid by {n} level year-end payments. "
            f"How much of payment {k} is interest "
            f"(PMT·(1−v^(n−k+1)))? Round to 2 decimals."
        )
        extra = {"loan": loan, "i": i, "n": n, "k": k}
    elif family == "principal_portion":
        answer = pmt * (1 + i) ** -(n - k + 1)
        wrongs = [pmt * (1 - (1 + i) ** -(n - k + 1)), pmt / n, pmt * i]
        statement = (
            f"A ${loan} loan at rate {i} is repaid by {n} level year-end payments. "
            f"How much of payment {k} is principal "
            f"(PMT·v^(n−k+1))? Round to 2 decimals."
        )
        extra = {"loan": loan, "i": i, "n": n, "k": k}
    elif family == "balloon":
        r = round(pmt + float(rng.uniform(5, 50)), 2)   # over-payment → drop final
        bal = loan * (1 + i) ** (n - 1) - r * _afv(i, n - 1)
        answer = bal * (1 + i)
        wrongs = [r, bal, r * (1 + i)]
        statement = (
            f"A ${loan} loan at rate {i} is repaid by payments of ${r} for "
            f"{n - 1} years, then a final (balloon/drop) payment at year {n} that "
            f"clears the balance. Find that final payment. Round to 2 decimals."
        )
        extra = {"loan": loan, "i": i, "n": n, "r": r}
    else:
        j = round(float(rng.uniform(0.02, i)), 3)
        deposit = loan / _afv(j, n)
        answer = loan * i + deposit
        wrongs = [loan * i, deposit, loan * i + loan / n]
        statement = (
            f"A ${loan} loan charges interest at {i}/year (paid annually). The "
            f"borrower also funds a sinking fund earning {j} to repay the ${loan} "
            f"principal in {n} years. Find the TOTAL annual outlay. "
            f"Round to 2 decimals."
        )
        extra = {"loan": loan, "i": i, "j": j, "n": n}

    return _result("fm_loan", family, statement, answer, wrongs, extra, seed, rng)


@register("fm_bond")
def gen_fm_bond(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    family = ask if ask in BOND else str(rng.choice(BOND))
    face = float(rng.choice([1000, 5000]))
    r = round(float(rng.uniform(0.03, 0.07)), 3)     # coupon rate / period
    i = round(float(rng.uniform(0.03, 0.07)), 3)     # yield / period
    n = int(rng.integers(5, 21))
    c = face                                          # redeem at par
    coupon = face * r
    price = coupon * _apv(i, n) + c * (1 + i) ** -n

    if family == "premium_discount":
        answer = price - c
        wrongs = [c - price, coupon * _apv(i, n), price]
        statement = (
            f"A {n}-year bond, face ${face:.0f}, coupon rate {r}, redeemed at par, "
            f"is priced at yield {i}. Find the premium (price − redemption); a "
            f"negative value is a discount. Round to 2 decimals."
        )
        extra = {"face": face, "r": r, "i": i, "n": n}
    elif family == "book_value":
        t = int(rng.integers(1, n))
        answer = coupon * _apv(i, n - t) + c * (1 + i) ** -(n - t)
        wrongs = [price, coupon * _apv(i, t) + c * (1 + i) ** -t, c]
        statement = (
            f"A {n}-year bond, face ${face:.0f}, coupon rate {r}, par redemption, "
            f"yield {i}. Find its book value just after coupon {t}. "
            f"Round to 2 decimals."
        )
        extra = {"face": face, "r": r, "i": i, "n": n, "t": t}
    elif family == "amort_premium":
        t = int(rng.integers(1, n + 1))
        bv_prev = coupon * _apv(i, n - t + 1) + c * (1 + i) ** -(n - t + 1)
        answer = coupon - i * bv_prev          # premium write-down in period t
        wrongs = [i * bv_prev, coupon, coupon - i * c]
        statement = (
            f"A {n}-year bond, face ${face:.0f}, coupon rate {r}, par, yield {i}. "
            f"Find the amortization of premium in coupon period {t} "
            f"(coupon − yield·prior book value). Round to 2 decimals."
        )
        extra = {"face": face, "r": r, "i": i, "n": n, "t": t}
    elif family == "accumulated_reinvest":
        j = round(float(rng.uniform(0.02, 0.06)), 3)
        answer = coupon * _afv(j, n) + c
        wrongs = [coupon * _afv(i, n) + c, coupon * n + c, coupon * _afv(j, n)]
        statement = (
            f"A {n}-year bond, face ${face:.0f}, coupon rate {r}, par. Coupons are "
            f"reinvested at {j}. Find the total accumulated value at maturity "
            f"(reinvested coupons + redemption). Round to 2 decimals."
        )
        extra = {"face": face, "r": r, "j": j, "n": n}
    elif family == "callable_price":
        n1 = int(rng.integers(5, 11))
        n2 = n1 + int(rng.integers(3, 8))
        p1 = coupon * _apv(i, n1) + c * (1 + i) ** -n1
        p2 = coupon * _apv(i, n2) + c * (1 + i) ** -n2
        answer = min(p1, p2)
        wrongs = [max(p1, p2), (p1 + p2) / 2, c]
        statement = (
            f"A bond, face ${face:.0f}, coupon rate {r}, par, is callable at year "
            f"{n1} or year {n2}. To guarantee a yield of at least {i}, find the "
            f"price (the minimum over call dates). Round to 2 decimals."
        )
        extra = {"face": face, "r": r, "i": i, "n1": n1, "n2": n2}
    else:
        answer = price
        wrongs = [coupon * _apv(i, n) + c, coupon * n + c, c * (1 + i) ** -n]
        statement = (
            f"A {n}-year bond has face/redemption ${face:.0f} and annual coupon "
            f"rate {r}, priced to yield {i}. Find its price "
            f"(coupons·a_n + redemption·vⁿ). Round to 2 decimals."
        )
        family = "price"
        extra = {"face": face, "r": r, "i": i, "n": n}

    return _result("fm_bond", family, statement, answer, wrongs, extra, seed, rng)


@register("fm_yield")
def gen_fm_yield(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    family = ask if ask in YIELD else str(rng.choice(YIELD))

    if family == "dollar_weighted":
        a = round(float(rng.uniform(1000, 5000)), 2)
        dep = round(float(rng.uniform(500, 2000)), 2)   # deposit at mid-year
        b = round(a + dep + float(rng.uniform(100, 800)), 2)
        answer = (b - a - dep) / (a + 0.5 * dep)
        wrongs = [(b - a - dep) / a, (b - a) / a, (b - a - dep) / (a + dep)]
        statement = (
            f"A fund starts the year at ${a}, receives a deposit of ${dep} at "
            f"mid-year, and ends at ${b}. Find the dollar-weighted yield "
            f"(simple-interest approximation). Round to 4 decimals."
        )
        extra = {"a": a, "dep": dep, "b": b}
    elif family == "time_weighted":
        a = round(float(rng.uniform(1000, 3000)), 2)
        mid = round(float(rng.uniform(1100, 3500)), 2)   # value just before deposit
        dep = round(float(rng.uniform(300, 1500)), 2)
        b = round((mid + dep) * float(rng.uniform(1.02, 1.12)), 2)
        answer = (mid / a) * (b / (mid + dep)) - 1
        wrongs = [(b - a - dep) / a, b / a - 1, (mid / a) * (b / mid) - 1]
        statement = (
            f"A fund is ${a} at time 0, grows to ${mid} just before a ${dep} "
            f"deposit at mid-year, and ends the year at ${b}. Find the "
            f"time-weighted yield. Round to 4 decimals."
        )
        extra = {"a": a, "mid": mid, "dep": dep, "b": b}
    else:
        p = round(float(rng.uniform(2000, 6000)), 2)
        c1 = round(float(rng.uniform(500, 2500)), 2)
        c2 = round(float(rng.uniform(500, 2500)), 2)
        c3 = round(p * float(rng.uniform(0.6, 1.2)), 2)
        cfs = [-p, c1, c2, c3]
        answer = _irr(cfs)
        wrongs = [(c1 + c2 + c3 - p) / p, answer + 0.02, answer / 2]
        statement = (
            f"An investment of ${p} returns ${c1}, ${c2}, ${c3} at the ends of "
            f"years 1, 2, 3. Find the yield rate (IRR). Round to 4 decimals."
        )
        family = "irr"
        extra = {"cfs": cfs}

    return _result("fm_yield", family, statement, answer, wrongs, extra, seed, rng)


@register("fm_termstructure")
def gen_fm_termstructure(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    family = ask if ask in TERM else str(rng.choice(TERM))

    if family == "pv_spot":
        spots = [round(float(rng.uniform(0.02, 0.06)), 3) for _ in range(3)]
        cfs = [round(float(rng.uniform(200, 1200)), 2) for _ in range(3)]
        pairs = list(zip(cfs, spots, strict=True))
        answer = sum(c / (1 + s) ** (t + 1) for t, (c, s) in enumerate(pairs))
        flat = spots[0]
        wrongs = [
            sum(c / (1 + flat) ** (t + 1) for t, c in enumerate(cfs)),
            sum(cfs),
            sum(c * (1 + s) ** (t + 1) for t, (c, s) in enumerate(pairs)),
        ]
        statement = (
            f"Annual spot rates are s₁={spots[0]}, s₂={spots[1]}, s₃={spots[2]}. "
            f"Cash flows ${cfs[0]}, ${cfs[1]}, ${cfs[2]} arrive at the ends of "
            f"years 1, 2, 3. Find the present value. Round to 2 decimals."
        )
        extra = {"spots": spots, "cfs": cfs}
    else:
        s1 = round(float(rng.uniform(0.02, 0.05)), 3)
        s2 = round(s1 + float(rng.uniform(0.003, 0.02)), 3)
        answer = (1 + s2) ** 2 / (1 + s1) - 1
        wrongs = [s2 - s1, (s1 + s2) / 2, (1 + s2) / (1 + s1) - 1]
        statement = (
            f"The 1-year spot rate is {s1} and the 2-year spot rate is {s2}. Find "
            f"the 1-year forward rate one year from now "
            f"(f = (1+s₂)²/(1+s₁) − 1). Round to 4 decimals."
        )
        extra = {"s1": s1, "s2": s2}

    return _result("fm_termstructure", family, statement, answer, wrongs, extra,
                   seed, rng)


@register("fm_duration")
def gen_fm_duration(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    family = ask if ask in DURATION else str(rng.choice(DURATION))
    i = round(float(rng.uniform(0.03, 0.08)), 3)
    times = [1, 2, 3, 4]
    cfs = [round(float(rng.uniform(100, 900)), 2) for _ in times]
    v = 1 / (1 + i)
    pv = [c * v ** t for c, t in zip(cfs, times, strict=True)]
    price = sum(pv)
    mac = sum(t * p for t, p in zip(times, pv, strict=True)) / price

    if family == "modified":
        answer = mac / (1 + i)
        wrongs = [mac, mac * (1 + i), price]
        label = "modified duration (Macaulay / (1+i))"
    elif family == "convexity":
        conv = sum(t * (t + 1) * c * v ** (t + 2)
                   for c, t in zip(cfs, times, strict=True))
        answer = conv / price
        wrongs = [mac, mac / (1 + i), price]
        label = "convexity (Σ t(t+1)·CFₜ·v^(t+2) / P)"
    elif family == "pv_change":
        di = round(float(rng.choice([0.01, -0.01, 0.005])), 3)
        moddur = mac / (1 + i)
        answer = -price * moddur * di
        wrongs = [-price * mac * di, price * moddur * di, -moddur * di]
        label = None
        statement = (
            f"A cash flow stream pays ${cfs[0]}, ${cfs[1]}, ${cfs[2]}, ${cfs[3]} at "
            f"the ends of years 1–4, valued at yield {i}. Estimate the change in "
            f"present value if the yield rises by {di} "
            f"(ΔP ≈ −P·ModDur·Δi). Round to 2 decimals."
        )
        extra = {"i": i, "cfs": cfs, "di": di}
        return _result("fm_duration", family, statement, answer, wrongs, extra,
                       seed, rng)
    else:
        answer = mac
        undisc = sum(t * c for t, c in zip(times, cfs, strict=True)) / sum(cfs)
        wrongs = [mac / (1 + i), price, undisc]
        label = "Macaulay duration (Σ t·PVₜ / Σ PVₜ)"

    statement = (
        f"A cash flow stream pays ${cfs[0]}, ${cfs[1]}, ${cfs[2]}, ${cfs[3]} at the "
        f"ends of years 1–4, valued at annual effective yield {i}. Find the "
        f"{label}. Round to 4 decimals."
    )
    extra = {"i": i, "cfs": cfs}
    return _result("fm_duration", family, statement, answer, wrongs, extra, seed, rng)
