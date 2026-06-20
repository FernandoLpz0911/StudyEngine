"""Worked solutions for MATH 250 set-counting problems."""
from __future__ import annotations

from engine.feedback.solve import register_solver


@register_solver("set_counting")
def worked_steps(kind: str, ask: str, params: dict) -> list[str]:
    if "n" in params:
        n = params["n"]
        return [
            "Each element is independently either in or out of a subset.",
            f"With |A| = {n}, that is 2^{n} = {2**n} subsets.",
        ]
    a, b, inter = params["a"], params["b"], params["inter"]
    return [
        "Inclusion–exclusion: |A ∪ B| = |A| + |B| − |A ∩ B|.",
        f"= {a} + {b} − {inter} = {a + b - inter}.",
    ]
