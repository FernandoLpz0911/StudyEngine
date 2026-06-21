"""Worked solutions for Exam FM problems (same closed forms as the generators)."""
from __future__ import annotations

from engine.feedback.solve import register_solver


@register_solver("fm_compound")
@register_solver("fm_annuity")
def worked_steps(kind: str, ask: str, params: dict) -> list[str]:
    if kind == "fm_compound":
        return _compound(params)
    return _annuity(ask, params)


def _compound(p: dict) -> list[str]:
    if "pv" in p:
        pv, i, n = p["pv"], p["i"], p["n"]
        ans = pv * (1 + i) ** n
        return [
            "Accumulated value: FV = PV·(1 + i)^n.",
            f"= {pv}·(1 + {i})^{n} = {round(ans, 2)}.",
        ]
    if "fv" in p:
        fv, i, n = p["fv"], p["i"], p["n"]
        ans = fv * (1 + i) ** -n
        return [
            "Present value: PV = FV·(1 + i)^(−n).",
            f"= {fv}·(1 + {i})^(−{n}) = {round(ans, 2)}.",
        ]
    nominal, m = p["nominal"], p["m"]
    ans = ((1 + nominal / m) ** m - 1) * 100
    return [
        "Effective annual rate: i = (1 + i^(m)/m)^m − 1.",
        f"= (1 + {nominal}/{m})^{m} − 1 = {round(ans, 2)}%.",
    ]


def _annuity(ask: str, p: dict) -> list[str]:
    i = p["i"]
    if "loan" in p:
        loan, n = p["loan"], p["n"]
        ans = loan * i / (1 - (1 + i) ** -n)
        return [
            "Level payment: PMT = L·i / (1 − (1 + i)^(−n)).",
            f"= {loan}·{i} / (1 − (1 + {i})^(−{n})) = {round(ans, 2)}.",
        ]
    if "n" not in p:
        pmt = p["pmt"]
        ans = pmt / i
        return [
            "Perpetuity-immediate present value: PV = PMT / i.",
            f"= {pmt} / {i} = {round(ans, 2)}.",
        ]
    pmt, n = p["pmt"], p["n"]
    if ask == "annuity_fv":
        ans = pmt * ((1 + i) ** n - 1) / i
        return [
            "Annuity-immediate accumulated value: FV = PMT·((1 + i)^n − 1)/i.",
            f"= {pmt}·((1 + {i})^{n} − 1)/{i} = {round(ans, 2)}.",
        ]
    ans = pmt * (1 - (1 + i) ** -n) / i
    return [
        "Annuity-immediate present value: PV = PMT·(1 − (1 + i)^(−n))/i.",
        f"= {pmt}·(1 − (1 + {i})^(−{n}))/{i} = {round(ans, 2)}.",
    ]
