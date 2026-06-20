"""MATH 250 generators — objective counting and truth-table problems.

Proofs themselves are open-ended, but the discrete-math facts that underpin them
(inclusion–exclusion, products, power sets, function counts, truth tables) have
closed-form answers and make good auto-graded drills.
"""
from __future__ import annotations

import numpy as np

from engine.generation.base import Problem, make_int_choices, register

SET_FAMILIES = ["union2", "powerset", "cartesian", "union3"]

# Two-variable connectives, evaluated over the four rows of a truth table.
CONNECTIVES = {
    "P ∧ Q": lambda p, q: p and q,
    "P ∨ Q": lambda p, q: p or q,
    "P → Q": lambda p, q: (not p) or q,
    "P ↔ Q": lambda p, q: p == q,
    "P ⊕ Q (exclusive or)": lambda p, q: p != q,
    "¬P ∧ Q": lambda p, q: (not p) and q,
}


def _true_rows(formula: str) -> int:
    fn = CONNECTIVES[formula]
    return sum(1 for p in (False, True) for q in (False, True) if fn(p, q))


@register("set_counting")
def gen_set_counting(ask: str, params: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    family = ask if ask in SET_FAMILIES else str(rng.choice(SET_FAMILIES))

    if family == "powerset":
        n = int(rng.integers(2, 7))
        answer = 2**n
        statement = (
            f"A set A has |A| = {n}. How many subsets does A have "
            f"(the size of its power set |P(A)|)?"
        )
        prefer = (2 * n, n * n, answer - 2)
        choices = make_int_choices(answer, rng, lo=1, hi=answer + n, prefer=prefer)
        return Problem("set_counting", family, statement, float(answer), choices,
                       params={"n": n}, seed=seed)

    if family == "cartesian":
        a = int(rng.integers(2, 9))
        b = int(rng.integers(2, 9))
        answer = a * b
        statement = (
            f"Sets A and B have |A| = {a} and |B| = {b}. What is |A × B| "
            f"(the size of their Cartesian product)?"
        )
        prefer = (a + b, a + b + 1, a * b - a)
        choices = make_int_choices(answer, rng, lo=1, hi=a * b + b, prefer=prefer)
        return Problem("set_counting", family, statement, float(answer), choices,
                       params={"a": a, "b": b}, seed=seed)

    if family == "union3":
        a, b, c = (int(rng.integers(5, 11)) for _ in range(3))
        triple = int(rng.integers(0, 3))
        ab = triple + int(rng.integers(0, 3))
        ac = triple + int(rng.integers(0, 3))
        bc = triple + int(rng.integers(0, 3))
        answer = a + b + c - ab - ac - bc + triple
        statement = (
            f"|A|={a}, |B|={b}, |C|={c}, |A∩B|={ab}, |A∩C|={ac}, |B∩C|={bc}, "
            f"|A∩B∩C|={triple}. By inclusion–exclusion, what is |A∪B∪C|?"
        )
        prefer = (a + b + c, a + b + c - ab - ac - bc, answer + triple)
        choices = make_int_choices(answer, rng, lo=0, hi=a + b + c, prefer=prefer)
        return Problem("set_counting", family, statement, float(answer), choices,
                       params={"a": a, "b": b, "c": c, "ab": ab, "ac": ac,
                               "bc": bc, "triple": triple}, seed=seed)

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
    return Problem("set_counting", "union2", statement, float(answer), choices,
                   params={"a": a, "b": b, "inter": inter}, seed=seed)


@register("truth_table")
def gen_truth_table(ask: str, params: dict, seed: int) -> Problem:
    """Count the rows of a two-variable truth table where the formula is true."""
    rng = np.random.default_rng(seed)
    formula = str(rng.choice(list(CONNECTIVES)))
    answer = _true_rows(formula)
    statement = (
        f"Over all four combinations of truth values for P and Q, in how many "
        f"rows is the formula  {formula}  true?"
    )
    return Problem(
        "truth_table", "true_rows", statement, float(answer),
        make_int_choices(answer, rng, lo=0, hi=4),
        params={"formula": formula}, seed=seed,
    )


@register("function_count")
def gen_function_count(ask: str, params: dict, seed: int) -> Problem:
    """Count functions from a size-m domain to a size-n codomain: nᵐ."""
    rng = np.random.default_rng(seed)
    m = int(rng.integers(1, 4))
    n = int(rng.integers(2, 5))
    answer = n**m
    statement = (
        f"How many functions are there from a set of size {m} to a set of "
        f"size {n}?"
    )
    prefer = (m * n, m**n, n**m - 1)
    choices = make_int_choices(answer, rng, lo=1, hi=answer + n, prefer=prefer)
    return Problem(
        "function_count", "count", statement, float(answer), choices,
        params={"m": m, "n": n}, seed=seed,
    )
