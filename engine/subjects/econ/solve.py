"""Worked solutions for ECON 111 decision problems."""
from __future__ import annotations

from engine.feedback.solve import register_solver


@register_solver("econ_decision")
def worked_steps(kind: str, ask: str, params: dict) -> list[str]:
    if "values" in params:
        values = params["values"]
        return [
            "Opportunity cost = the value of the single next-best alternative given up.",
            f"You take the best (${values[0]}); the next best is ${values[1]}.",
            f"Opportunity cost = ${values[1]} (the lowest option is irrelevant).",
        ]
    if "mb" in params:
        mb, mc = params["mb"], params["mc"]
        return [
            "Decide at the margin: net benefit = marginal benefit − marginal cost.",
            f"= ${mb} − ${mc} = ${mb - mc}.",
        ]
    if "old" in params:
        old, new = params["old"], params["new"]
        return [
            "Percentage change = (new − old) / old × 100.",
            f"= ({new} − {old}) / {old} × 100 = {round((new - old) / old * 100, 2)}%.",
        ]
    if "cost" in params:
        cost, gain = params["cost"], params["gain"]
        return [
            "ROI = (gain − cost) / cost × 100.",
            f"= ({gain} − {cost}) / {cost} × 100 = {round((gain - cost) / cost * 100, 2)}%.",
        ]
    if "dq" in params:
        dq, dp = params["dq"], params["dp"]
        return [
            "Price elasticity (magnitude) = |%ΔQ / %ΔP|.",
            f"= |{dq} / {dp}| = {round(abs(dq / dp), 2)}.",
        ]

    pct, win = params["pct"], params["win"]
    ev = round(pct / 100 * win, 2)
    return [
        "Expected value = probability × payoff (the $0 outcome adds nothing).",
        f"= {pct}% × ${win} = {pct / 100} × {win} = ${ev}.",
    ]
