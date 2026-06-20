"""ECON 111 generators — objective decision problems (opportunity cost, margin, EV).

Freakonomics is mostly qualitative, but its core decision rules are quantitative
and auto-gradeable: opportunity cost, marginal benefit vs cost, expected value.
"""
from __future__ import annotations

import numpy as np

from engine.generation.base import Problem, make_int_choices, make_mc_choices, register

FAMILIES = ["opportunity_cost", "marginal_net", "expected_value"]


@register("econ_decision")
def gen_econ_decision(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    family = ask if ask in FAMILIES else str(rng.choice(FAMILIES))

    if family == "opportunity_cost":
        values = sorted(
            (int(v) for v in rng.choice(range(10, 100), size=3, replace=False)),
            reverse=True,
        )
        answer = values[1]  # value of the next-best option you give up
        statement = (
            f"With one free hour you could earn ${values[0]}, ${values[1]}, or "
            f"${values[2]}. You take the most valuable. What is the opportunity "
            f"cost of that choice?"
        )
        prefer = (values[0], values[2], values[0] + values[2])
        choices = make_int_choices(answer, rng, lo=10, hi=sum(values), prefer=prefer)
        return Problem("econ_decision", family, statement, float(answer), choices,
                       params={"values": values}, seed=seed)

    if family == "marginal_net":
        mb = int(rng.integers(8, 30))
        mc = int(rng.integers(1, mb))
        answer = mb - mc
        statement = (
            f"Producing one more unit yields marginal benefit ${mb} and marginal "
            f"cost ${mc}. What is the net benefit of producing that unit?"
        )
        prefer = (mb + mc, mb, mc)
        choices = make_int_choices(answer, rng, lo=0, hi=mb + mc, prefer=prefer)
        return Problem("econ_decision", family, statement, float(answer), choices,
                       params={"mb": mb, "mc": mc}, seed=seed)

    pct = int(rng.integers(10, 90))
    win = int(rng.integers(2, 20)) * 10
    answer = round(pct / 100 * win, 2)
    statement = (
        f"A bet pays ${win} with probability {pct}%, otherwise $0. "
        f"What is its expected value? Round to 2 decimals."
    )
    wrongs = [float(win), float(pct), round((1 - pct / 100) * win, 2)]
    choices = make_mc_choices(answer, wrongs, rng)
    return Problem("econ_decision", family, statement, round(answer, 3), choices,
                   params={"pct": pct, "win": win}, seed=seed)
