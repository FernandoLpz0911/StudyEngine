"""Exam FM (Financial Mathematics) generators — closed-form time-value-of-money.

Compound interest and annuity values are exact functions of (rate, periods,
payment), so each answer and its worked solution share one computation.
"""
from __future__ import annotations

import numpy as np

from engine.generation.base import Problem, make_mc_choices, register

COMPOUND = ["future_value", "present_value", "effective_rate"]
ANNUITY = ["annuity_pv", "annuity_fv", "perpetuity", "loan_payment"]


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
    else:
        nominal = round(float(rng.uniform(0.04, 0.12)), 3)
        m = int(rng.choice([2, 4, 12]))
        answer = ((1 + nominal / m) ** m - 1) * 100
        wrongs = [nominal * 100, ((1 + nominal) ** m - 1) * 100, nominal / m * 100]
        statement = (
            f"A nominal annual rate of {nominal} is compounded {m} times per year. "
            f"What is the annual effective rate, as a percentage? Round to 2 decimals."
        )
        extra = {"nominal": nominal, "m": m}

    return Problem(
        "fm_compound", family, statement, round(answer, 3),
        make_mc_choices(answer, wrongs, rng),
        params=extra, seed=seed,
    )


@register("fm_annuity")
def gen_fm_annuity(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    family = ask if ask in ANNUITY else str(rng.choice(ANNUITY))
    i = round(float(rng.uniform(0.03, 0.10)), 3)
    n = int(rng.integers(3, 21))
    pmt = round(float(rng.uniform(100, 1000)), 2)

    if family == "annuity_pv":
        answer = pmt * (1 - (1 + i) ** -n) / i
        wrongs = [pmt * (1 - (1 + i) ** -n), pmt * n, pmt / i]
        statement = (
            f"An annuity-immediate pays ${pmt} at the end of each year for {n} "
            f"years at annual effective rate {i}. Find its present value. "
            f"Round to 2 decimals."
        )
        extra = {"pmt": pmt, "i": i, "n": n}
    elif family == "annuity_fv":
        answer = pmt * ((1 + i) ** n - 1) / i
        wrongs = [pmt * ((1 + i) ** n - 1), pmt * n, pmt * (1 + i) ** n]
        statement = (
            f"An annuity-immediate pays ${pmt} at the end of each year for {n} "
            f"years at annual effective rate {i}. Find its accumulated value. "
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
    else:
        loan = round(float(rng.uniform(2000, 20000)), 2)
        answer = loan * i / (1 - (1 + i) ** -n)
        wrongs = [loan / n, loan * i, loan * i / (1 - (1 + i) ** n)]
        statement = (
            f"A loan of ${loan} is repaid with level annual payments over {n} "
            f"years at annual effective rate {i}. Find the annual payment. "
            f"Round to 2 decimals."
        )
        extra = {"loan": loan, "i": i, "n": n}

    return Problem(
        "fm_annuity", family, statement, round(answer, 3),
        make_mc_choices(answer, wrongs, rng),
        params=extra, seed=seed,
    )
