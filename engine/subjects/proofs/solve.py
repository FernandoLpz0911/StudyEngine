"""Worked solutions for the MATH 215 objective drills."""
from __future__ import annotations

from math import comb, factorial, gcd, perm

from engine.feedback.solve import register_solver
from engine.subjects.proofs.generators import (
    CONNECTIVES,
    CONNECTIVES3,
    _least_prime_factor,
    _true_rows,
    _true_rows3,
)


@register_solver("set_counting")
def solve_set_counting(kind: str, ask: str, params: dict) -> list[str]:
    if ask == "powerset":
        n = params["n"]
        return ["Each element is independently in or out of a subset.",
                f"So |P(A)| = 2^{n} = {2**n}."]
    if ask == "cartesian":
        a, b = params["a"], params["b"]
        return ["A × B pairs every element of A with every element of B.",
                f"So |A × B| = {a}·{b} = {a * b}."]
    if ask == "union3":
        a, b, c = params["a"], params["b"], params["c"]
        ab, ac, bc, t = params["ab"], params["ac"], params["bc"], params["triple"]
        return ["|A∪B∪C| = Σ|A| − Σ|pairwise ∩| + |A∩B∩C|.",
                f"= ({a}+{b}+{c}) − ({ab}+{ac}+{bc}) + {t} "
                f"= {a + b + c - ab - ac - bc + t}."]
    if ask == "intersection":
        a, b, u = params["a"], params["b"], params["union"]
        return ["Rearrange |A∪B| = |A| + |B| − |A∩B| to |A∩B| = |A|+|B|−|A∪B|.",
                f"= {a} + {b} − {u} = {a + b - u}."]
    if ask == "difference":
        b, inter = params["b"], params["inter"]
        return ["B − A removes the part of B that meets A: |B−A| = |B| − |A∩B|.",
                f"= {b} − {inter} = {b - inter}."]
    if ask == "offdiag":
        n = params["n"]
        return [f"There are {n}·{n} = {n * n} ordered pairs in A × A.",
                f"Remove the {n} pairs with x = y: {n * n} − {n} = {n * n - n}."]
    a, b, inter = params["a"], params["b"], params["inter"]
    return ["Inclusion–exclusion: |A ∪ B| = |A| + |B| − |A ∩ B|.",
            f"= {a} + {b} − {inter} = {a + b - inter}."]


@register_solver("truth_table")
def solve_truth_table(kind: str, ask: str, params: dict) -> list[str]:
    formula = params["formula"]
    if params.get("nvars") == 3:
        fn = CONNECTIVES3[formula]
        trues = [
            f"({int(p)}{int(q)}{int(r)})"
            for p in (False, True) for q in (False, True) for r in (False, True)
            if fn(p, q, r)
        ]
        count = _true_rows3(formula)
        verdict = ("a tautology" if count == 8
                   else "a contradiction" if count == 0 else "neither")
        return [f"Evaluate {formula} on all 8 rows (P Q R).",
                f"True in: {', '.join(trues) or 'no rows'}.",
                f"Count = {count}, so the formula is {verdict}."]
    fn = CONNECTIVES[formula]
    trues = [f"(P={int(p)},Q={int(q)})"
             for p in (False, True) for q in (False, True) if fn(p, q)]
    count = _true_rows(formula)
    verdict = ("a tautology" if count == 4
               else "a contradiction" if count == 0 else "neither")
    return [f"Evaluate {formula} on all four rows.",
            f"True in: {', '.join(trues) or 'no rows'}.",
            f"Count = {count}, so the formula is {verdict}."]


@register_solver("function_count")
def solve_function_count(kind: str, ask: str, params: dict) -> list[str]:
    if ask == "injections":
        m, n = params["m"], params["n"]
        if m > n:
            return ["An injection needs distinct images, but the domain is larger "
                    f"than the codomain ({m} > {n}).", "So there are 0 injections."]
        return ["The first domain element has n choices, the next n−1, and so on "
                "(images must stay distinct).",
                f"So the count is n!/(n−m)! = P({n},{m}) = {perm(n, m)}."]
    if ask == "bijections":
        n = params["n"]
        return ["A bijection between equal-size sets is a permutation of the "
                "targets.", f"So the count is {n}! = {factorial(n)}."]
    m, n = params["m"], params["n"]
    return ["Each of the m domain elements maps independently to one of n targets.",
            f"So the count is n^m = {n}^{m} = {n**m}."]


@register_solver("number_theory")
def solve_number_theory(kind: str, ask: str, params: dict) -> list[str]:
    if ask == "divides":
        a, b = params["a"], params["b"]
        yes = b % a == 0
        return [f"a divides b iff b mod a = 0. Here {b} mod {a} = {b % a}.",
                f"So {a} {'divides' if yes else 'does not divide'} {b} "
                f"→ {1 if yes else 0}."]
    if ask == "gcd":
        a, b = params["a"], params["b"]
        return ["Use the Euclidean algorithm (repeated remainders).",
                f"gcd({a}, {b}) = {gcd(a, b)}."]
    if ask == "least_prime_factor":
        n = params["n"]
        lpf = _least_prime_factor(n)
        return [f"Test primes 2, 3, 5, … in turn for divisibility into {n}.",
                f"The smallest that divides {n} is {lpf}."]
    b, m = params["b"], params["m"]
    return [f"Divide {b} by {m}: quotient {b // m}, remainder {b % m}.",
            f"So {b} mod {m} = {b % m}."]


@register_solver("modular")
def solve_modular(kind: str, ask: str, params: dict) -> list[str]:
    m = params["m"]
    if ask == "mul":
        a, b = params["a"], params["b"]
        return [f"({a} · {b}) = {a * b}; reduce mod {m}.",
                f"= {(a * b) % m}."]
    if ask == "pow":
        a, k = params["a"], params["k"]
        return [f"{a}^{k} = {a ** k}; reduce mod {m}.",
                f"= {pow(a, k, m)}."]
    a, b = params["a"], params["b"]
    return [f"({a} + {b}) = {a + b}; reduce mod {m}.",
            f"= {(a + b) % m}."]


@register_solver("combinatorics")
def solve_combinatorics(kind: str, ask: str, params: dict) -> list[str]:
    if ask == "combination":
        n, r = params["n"], params["r"]
        return ["Order doesn't matter, so use the binomial coefficient.",
                f"C({n},{r}) = {n}!/({r}!·{n - r}!) = {comb(n, r)}."]
    if ask == "circular":
        n = params["n"]
        return [f"Fix one of the {n} people to kill rotation symmetry; arrange "
                "the rest.", f"So ({n}−1)! = {factorial(n - 1)}."]
    n, r = params["n"], params["r"]
    return ["Order matters, so use permutations.",
            f"P({n},{r}) = {n}!/{n - r}! = {perm(n, r)}."]


@register_solver("pigeonhole")
def solve_pigeonhole(kind: str, ask: str, params: dict) -> list[str]:
    if ask == "guaranteed":
        n, k = params["n"], params["k"]
        return ["By pigeonhole, some box holds at least ⌈items/boxes⌉.",
                f"= ⌈{n}/{k}⌉ = {-(-n // k)}."]
    k = params["k"]
    return [f"With {k} boxes, {k} items could land one per box (no repeat).",
            f"One more forces a repeat: {k} + 1 = {k + 1}."]


@register_solver("induction_sum")
def solve_induction_sum(kind: str, ask: str, params: dict) -> list[str]:
    n = params["n"]
    if ask == "sum_i2":
        return ["Σ i² = n(n+1)(2n+1)/6.",
                f"= {n}·{n + 1}·{2 * n + 1}/6 = {n * (n + 1) * (2 * n + 1) // 6}."]
    if ask == "sum_cubes":
        return ["Σ i³ = (n(n+1)/2)² (the square of the triangular number).",
                f"= ({n * (n + 1) // 2})² = {(n * (n + 1) // 2) ** 2}."]
    if ask == "sum_odd":
        return ["The sum of the first n odd numbers is n².",
                f"= {n}² = {n * n}."]
    return ["Σ i = n(n+1)/2 (pair the ends; Gauss's trick).",
            f"= {n}·{n + 1}/2 = {n * (n + 1) // 2}."]


@register_solver("floor")
def solve_floor(kind: str, ask: str, params: dict) -> list[str]:
    if ask == "count_multiples":
        n, d = params["n"], params["d"]
        return [f"The multiples of {d} up to {n} are {d}, 2·{d}, …; there are "
                f"⌊{n}/{d}⌋ of them.", f"= {n // d}."]
    p, q = params["p"], params["q"]
    return [f"⌊{p}/{q}⌋ is the greatest integer ≤ {p}/{q} = {p / q:.3f}.",
            f"= {p // q}."]
