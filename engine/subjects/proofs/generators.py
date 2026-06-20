"""MATH 250 generators — objective set-counting problems.

Proofs themselves are open-ended, but the counting facts that underpin them
(inclusion–exclusion, power-set size) have closed-form answers and make good
auto-graded drills.
"""
from __future__ import annotations

import numpy as np

from engine.generation.base import Problem, make_int_choices, register


@register("set_counting")
def gen_set_counting(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    family = ask if ask in ("union2", "powerset") else str(
        rng.choice(["union2", "powerset"])
    )

    if family == "powerset":
        n = int(rng.integers(2, 7))
        answer = 2**n
        statement = (
            f"A set A has |A| = {n}. How many subsets does A have "
            f"(the size of its power set |P(A)|)?"
        )
        prefer = (2 * n, n * n, answer - 2)
        choices = make_int_choices(answer, rng, lo=1, hi=answer + n, prefer=prefer)
        extra = {"n": n}
    else:
        a = int(rng.integers(3, 9))
        b = int(rng.integers(3, 9))
        inter = int(rng.integers(1, min(a, b) + 1))
        answer = a + b - inter
        statement = (
            f"Sets A and B satisfy |A| = {a}, |B| = {b}, and |A ∩ B| = {inter}. "
            f"By inclusion–exclusion, what is |A ∪ B|?"
        )
        prefer = (a + b, a + b + inter, a + b - 2 * inter)
        choices = make_int_choices(answer, rng, lo=0, hi=a + b, prefer=prefer)
        extra = {"a": a, "b": b, "inter": inter}

    return Problem("set_counting", family, statement, float(answer), choices,
                   params=extra, seed=seed)
