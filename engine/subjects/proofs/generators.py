"""MATH 215 generators — objective drills underpinning the proof topics.

Proofs themselves are open-ended, but the discrete-math facts behind them
(truth tables, divisibility/modular arithmetic, set and function counting,
combinatorics, the pigeonhole bound, induction summation formulas, the floor
function) have closed-form answers and make good auto-graded practice.
"""
from __future__ import annotations

from math import comb, factorial, gcd, perm

import numpy as np

from engine.generation.base import Problem, make_int_choices, register

SET_FAMILIES = ["union2", "powerset", "cartesian", "union3",
                "intersection", "difference", "offdiag"]

# Two-variable connectives, evaluated over the four rows of a truth table.
CONNECTIVES = {
    "P ∧ Q": lambda p, q: p and q,
    "P ∨ Q": lambda p, q: p or q,
    "P → Q": lambda p, q: (not p) or q,
    "P ↔ Q": lambda p, q: p == q,
    "P ⊕ Q (exclusive or)": lambda p, q: p != q,
    "¬P ∧ Q": lambda p, q: (not p) and q,
}

# Three-variable formulas, evaluated over the eight rows of a truth table.
CONNECTIVES3 = {
    "(P ∧ Q) ∨ R": lambda p, q, r: (p and q) or r,
    "(P → Q) ∧ (Q → R)": lambda p, q, r: ((not p) or q) and ((not q) or r),
    "¬P ∨ (Q ∧ R)": lambda p, q, r: (not p) or (q and r),
    "(P ∨ Q) → R": lambda p, q, r: (not (p or q)) or r,
    "P ↔ (Q ∨ R)": lambda p, q, r: p == (q or r),
}


def _true_rows(formula: str) -> int:
    fn = CONNECTIVES[formula]
    return sum(1 for p in (False, True) for q in (False, True) if fn(p, q))


def _true_rows3(formula: str) -> int:
    fn = CONNECTIVES3[formula]
    return sum(
        1
        for p in (False, True)
        for q in (False, True)
        for r in (False, True)
        if fn(p, q, r)
    )


def _least_prime_factor(n: int) -> int:
    d = 2
    while d * d <= n:
        if n % d == 0:
            return d
        d += 1
    return n


def _binary_choices(answer: int, rng: np.random.Generator) -> list[str]:
    """Two shuffled options for a yes/no (1/0) generator."""
    opts = [f"{float(answer):.3f}", f"{float(1 - answer):.3f}"]
    order = rng.permutation(2)
    return [opts[i] for i in order]


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

    if family == "intersection":
        a = int(rng.integers(4, 10))
        b = int(rng.integers(4, 10))
        inter = int(rng.integers(1, min(a, b) + 1))
        union = a + b - inter
        answer = inter
        statement = (
            f"Sets A and B satisfy |A| = {a}, |B| = {b}, and |A ∪ B| = {union}. "
            f"What is |A ∩ B|?"
        )
        prefer = (union - a, union - b, a + b - union - 1)
        choices = make_int_choices(answer, rng, lo=0, hi=min(a, b), prefer=prefer)
        return Problem("set_counting", family, statement, float(answer), choices,
                       params={"a": a, "b": b, "union": union}, seed=seed)

    if family == "difference":
        b = int(rng.integers(5, 12))
        inter = int(rng.integers(1, b))
        answer = b - inter
        statement = (
            f"Sets A and B satisfy |B| = {b} and |A ∩ B| = {inter}. "
            f"What is |B − A|?"
        )
        prefer = (b, b + inter, inter)
        choices = make_int_choices(answer, rng, lo=0, hi=b, prefer=prefer)
        return Problem("set_counting", family, statement, float(answer), choices,
                       params={"b": b, "inter": inter}, seed=seed)

    if family == "offdiag":
        n = int(rng.integers(3, 9))
        answer = n * n - n
        statement = (
            f"A set A has |A| = {n}. How many ordered pairs ⟨x, y⟩ ∈ A × A "
            f"have x ≠ y?"
        )
        prefer = (n * n, n * n - 1, n * (n - 1) // 2)
        choices = make_int_choices(answer, rng, lo=0, hi=n * n, prefer=prefer)
        return Problem("set_counting", family, statement, float(answer), choices,
                       params={"n": n}, seed=seed)

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
    """Count the rows of a truth table where the formula is true."""
    rng = np.random.default_rng(seed)
    if ask == "count_true":
        formula = str(rng.choice(list(CONNECTIVES3)))
        answer = _true_rows3(formula)
        statement = (
            f"Over all eight combinations of truth values for P, Q, R, in how "
            f"many rows is the formula  {formula}  true?  "
            f"(0 = contradiction, 8 = tautology.)"
        )
        return Problem(
            "truth_table", "count_true", statement, float(answer),
            make_int_choices(answer, rng, lo=0, hi=8),
            params={"formula": formula, "nvars": 3}, seed=seed,
        )
    formula = str(rng.choice(list(CONNECTIVES)))
    answer = _true_rows(formula)
    statement = (
        f"Over all four combinations of truth values for P and Q, in how many "
        f"rows is the formula  {formula}  true?  "
        f"(0 = contradiction, 4 = tautology.)"
    )
    return Problem(
        "truth_table", "true_rows", statement, float(answer),
        make_int_choices(answer, rng, lo=0, hi=4),
        params={"formula": formula, "nvars": 2}, seed=seed,
    )


@register("function_count")
def gen_function_count(ask: str, params: dict, seed: int) -> Problem:
    """Count functions / injections / bijections between finite sets."""
    rng = np.random.default_rng(seed)

    if ask == "injections":
        n = int(rng.integers(3, 7))   # codomain
        m = int(rng.integers(2, 5))   # domain
        answer = perm(n, m) if m <= n else 0
        statement = (
            f"How many injective (one-to-one) functions are there from a set of "
            f"size {m} to a set of size {n}?"
        )
        prefer = (n**m, comb(n, m), m**n)
        choices = make_int_choices(answer, rng, lo=0, hi=n**m, prefer=prefer)
        return Problem("function_count", "injections", statement, float(answer),
                       choices, params={"m": m, "n": n}, seed=seed)

    if ask == "bijections":
        n = int(rng.integers(3, 7))
        answer = factorial(n)
        statement = (
            f"How many bijections (one-to-one correspondences) are there between "
            f"two sets each of size {n}?"
        )
        prefer = (n * n, n**n, factorial(n - 1))
        choices = make_int_choices(answer, rng, lo=1, hi=factorial(n) + n,
                                   prefer=prefer)
        return Problem("function_count", "bijections", statement, float(answer),
                       choices, params={"n": n}, seed=seed)

    m = int(rng.integers(1, 4))
    n = int(rng.integers(2, 5))
    answer = n**m
    statement = (
        f"How many functions are there from a set of size {m} to a set of "
        f"size {n}?"
    )
    prefer = (m * n, m**n, n**m - 1)
    choices = make_int_choices(answer, rng, lo=1, hi=answer + n, prefer=prefer)
    return Problem("function_count", "count", statement, float(answer), choices,
                   params={"m": m, "n": n}, seed=seed)


@register("number_theory")
def gen_number_theory(ask: str, params: dict, seed: int) -> Problem:
    """Divisibility, remainders, gcd, and least prime factor."""
    rng = np.random.default_rng(seed)

    if ask == "divides":
        a = int(rng.integers(2, 10))
        if rng.random() < 0.5:
            b = a * int(rng.integers(2, 9))           # divisible
        else:
            b = a * int(rng.integers(2, 9)) + int(rng.integers(1, a))
        answer = 1 if b % a == 0 else 0
        statement = f"Does {a} divide {b}?  (1 = yes, 0 = no.)"
        return Problem("number_theory", "divides", statement, float(answer),
                       _binary_choices(answer, rng),
                       params={"a": a, "b": b}, seed=seed)

    if ask == "gcd":
        a = int(rng.integers(6, 49))
        b = int(rng.integers(6, 49))
        answer = gcd(a, b)
        statement = f"What is gcd({a}, {b}), the greatest common divisor?"
        prefer = (min(a, b), a * b // gcd(a, b), 1)
        choices = make_int_choices(answer, rng, lo=1, hi=min(a, b), prefer=prefer)
        return Problem("number_theory", "gcd", statement, float(answer), choices,
                       params={"a": a, "b": b}, seed=seed)

    if ask == "least_prime_factor":
        n = int(rng.integers(10, 61))
        while _least_prime_factor(n) == n:   # ensure composite for a real factor
            n = int(rng.integers(10, 61))
        answer = _least_prime_factor(n)
        statement = (
            f"What is the smallest prime that divides {n} "
            f"(its least prime factor)?"
        )
        prefer = (n // answer, answer + 1, 1)
        choices = make_int_choices(answer, rng, lo=2, hi=n // 2, prefer=prefer)
        return Problem("number_theory", "least_prime_factor", statement,
                       float(answer), choices, params={"n": n}, seed=seed)

    b = int(rng.integers(10, 100))
    m = int(rng.integers(2, 10))
    answer = b % m
    statement = f"What is {b} mod {m} (the remainder of {b} divided by {m})?"
    choices = make_int_choices(answer, rng, lo=0, hi=m - 1)
    return Problem("number_theory", "mod", statement, float(answer), choices,
                   params={"b": b, "m": m}, seed=seed)


@register("modular")
def gen_modular(ask: str, params: dict, seed: int) -> Problem:
    """Modular arithmetic: sum, product, or power reduced mod m."""
    rng = np.random.default_rng(seed)
    m = int(rng.integers(3, 13))
    a = int(rng.integers(3, 21))
    if ask == "mul":
        b = int(rng.integers(3, 21))
        answer = (a * b) % m
        statement = f"Compute (a · b) mod m for a = {a}, b = {b}, m = {m}."
        params_out = {"a": a, "b": b, "m": m}
    elif ask == "pow":
        k = int(rng.integers(2, 6))
        answer = pow(a, k, m)
        statement = f"Compute a^k mod m for a = {a}, k = {k}, m = {m}."
        params_out = {"a": a, "k": k, "m": m}
    else:
        b = int(rng.integers(3, 21))
        answer = (a + b) % m
        statement = f"Compute (a + b) mod m for a = {a}, b = {b}, m = {m}."
        ask = "add"
        params_out = {"a": a, "b": b, "m": m}
    choices = make_int_choices(answer, rng, lo=0, hi=m - 1)
    return Problem("modular", ask, statement, float(answer), choices,
                   params=params_out, seed=seed)


@register("combinatorics")
def gen_combinatorics(ask: str, params: dict, seed: int) -> Problem:
    """Permutations, combinations, and circular arrangements."""
    rng = np.random.default_rng(seed)

    if ask == "combination":
        n = int(rng.integers(4, 10))
        r = int(rng.integers(2, n))
        answer = comb(n, r)
        statement = (
            f"In how many ways can you choose {r} items from {n} when order "
            f"does NOT matter (C({n}, {r}))?"
        )
        prefer = (perm(n, r), comb(n, r - 1), n * r)
        choices = make_int_choices(answer, rng, lo=1, hi=perm(n, r), prefer=prefer)
        return Problem("combinatorics", "combination", statement, float(answer),
                       choices, params={"n": n, "r": r}, seed=seed)

    if ask == "circular":
        n = int(rng.integers(3, 8))
        answer = factorial(n - 1)
        statement = (
            f"In how many distinct ways can {n} people be seated around a "
            f"circular table (rotations counted as the same)?"
        )
        prefer = (factorial(n), n, factorial(n - 2))
        choices = make_int_choices(answer, rng, lo=1, hi=factorial(n),
                                   prefer=prefer)
        return Problem("combinatorics", "circular", statement, float(answer),
                       choices, params={"n": n}, seed=seed)

    n = int(rng.integers(4, 10))
    r = int(rng.integers(2, n))
    answer = perm(n, r)
    statement = (
        f"In how many ways can you arrange {r} of {n} items in order "
        f"(P({n}, {r}))?"
    )
    prefer = (comb(n, r), n**r, perm(n, r - 1))
    choices = make_int_choices(answer, rng, lo=1, hi=n**r, prefer=prefer)
    return Problem("combinatorics", "permutation", statement, float(answer),
                   choices, params={"n": n, "r": r}, seed=seed)


@register("pigeonhole")
def gen_pigeonhole(ask: str, params: dict, seed: int) -> Problem:
    """The pigeonhole bound: forcing a repeat, or the guaranteed maximum."""
    rng = np.random.default_rng(seed)

    if ask == "guaranteed":
        k = int(rng.integers(3, 10))     # boxes
        n = int(rng.integers(k + 1, 5 * k))  # items
        answer = -(-n // k)              # ceil(n/k)
        statement = (
            f"If {n} items are placed into {k} boxes, some box must contain at "
            f"least how many items?"
        )
        prefer = (n // k, n - k, k)
        choices = make_int_choices(answer, rng, lo=1, hi=n, prefer=prefer)
        return Problem("pigeonhole", "guaranteed", statement, float(answer),
                       choices, params={"n": n, "k": k}, seed=seed)

    k = int(rng.integers(3, 13))         # boxes
    answer = k + 1
    statement = (
        f"There are {k} boxes. What is the minimum number of items that "
        f"guarantees some box holds at least two?"
    )
    prefer = (k, 2 * k, k - 1)
    choices = make_int_choices(answer, rng, lo=2, hi=2 * k, prefer=prefer)
    return Problem("pigeonhole", "min_force", statement, float(answer), choices,
                   params={"k": k}, seed=seed)


@register("induction_sum")
def gen_induction_sum(ask: str, params: dict, seed: int) -> Problem:
    """Evaluate the closed forms proved by induction at a given n."""
    rng = np.random.default_rng(seed)
    n = int(rng.integers(3, 13))

    if ask == "sum_i2":
        answer = n * (n + 1) * (2 * n + 1) // 6
        statement = f"Evaluate 1² + 2² + … + {n}² (i.e. Σ i² for i = 1..{n})."
    elif ask == "sum_cubes":
        answer = (n * (n + 1) // 2) ** 2
        statement = f"Evaluate 1³ + 2³ + … + {n}³ (i.e. Σ i³ for i = 1..{n})."
    elif ask == "sum_odd":
        answer = n * n
        statement = (
            f"Evaluate the sum of the first {n} odd numbers "
            f"(1 + 3 + … + {2 * n - 1})."
        )
    else:
        ask = "sum_i"
        answer = n * (n + 1) // 2
        statement = f"Evaluate 1 + 2 + … + {n} (i.e. Σ i for i = 1..{n})."

    prefer = (answer - n, answer + n, n * n)
    choices = make_int_choices(answer, rng, lo=1, hi=answer + 2 * n, prefer=prefer)
    return Problem("induction_sum", ask, statement, float(answer), choices,
                   params={"n": n}, seed=seed)


@register("floor")
def gen_floor(ask: str, params: dict, seed: int) -> Problem:
    """The floor function: value of ⌊p/q⌋, or counting multiples in a range."""
    rng = np.random.default_rng(seed)

    if ask == "count_multiples":
        n = int(rng.integers(10, 51))
        d = int(rng.integers(2, 10))
        answer = n // d
        statement = (
            f"How many multiples of {d} are there in {{1, 2, …, {n}}} "
            f"(i.e. ⌊{n}/{d}⌋)?"
        )
        prefer = (n // d + 1, n // d - 1, d)
        choices = make_int_choices(answer, rng, lo=0, hi=n, prefer=prefer)
        return Problem("floor", "count_multiples", statement, float(answer),
                       choices, params={"n": n, "d": d}, seed=seed)

    p = int(rng.integers(7, 61))
    q = int(rng.integers(2, 10))
    answer = p // q
    statement = f"What is ⌊{p}/{q}⌋ (the floor of {p} divided by {q})?"
    prefer = (answer + 1, -(-p // q), answer - 1)
    choices = make_int_choices(answer, rng, lo=0, hi=p, prefer=prefer)
    return Problem("floor", "floor_val", statement, float(answer), choices,
                   params={"p": p, "q": q}, seed=seed)
