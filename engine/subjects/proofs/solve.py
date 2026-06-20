"""Worked solutions for MATH 250 counting and truth-table problems."""
from __future__ import annotations

from engine.feedback.solve import register_solver
from engine.subjects.proofs.generators import CONNECTIVES, _true_rows


@register_solver("set_counting")
@register_solver("truth_table")
@register_solver("function_count")
def worked_steps(kind: str, ask: str, params: dict) -> list[str]:
    if kind == "truth_table":
        formula = params["formula"]
        rows = [
            (p, q, CONNECTIVES[formula](p, q))
            for p in (False, True)
            for q in (False, True)
        ]
        trues = [f"(P={int(p)},Q={int(q)})" for p, q, val in rows if val]
        return [
            f"Evaluate {formula} on all four rows.",
            f"True in: {', '.join(trues) or 'no rows'}.",
            f"Count = {_true_rows(formula)}.",
        ]

    if kind == "function_count":
        m, n = params["m"], params["n"]
        return [
            "Each of the m domain elements maps independently to one of n targets.",
            f"So the count is n^m = {n}^{m} = {n**m}.",
        ]

    if "triple" in params:
        a, b, c = params["a"], params["b"], params["c"]
        ab, ac, bc, t = params["ab"], params["ac"], params["bc"], params["triple"]
        total = a + b + c - ab - ac - bc + t
        return [
            "Inclusion–exclusion: |A∪B∪C| = Σ|A| − Σ|pairwise ∩| + |A∩B∩C|.",
            f"= ({a}+{b}+{c}) − ({ab}+{ac}+{bc}) + {t} = {total}.",
        ]

    if "inter" in params:
        a, b, inter = params["a"], params["b"], params["inter"]
        return [
            "Inclusion–exclusion: |A ∪ B| = |A| + |B| − |A ∩ B|.",
            f"= {a} + {b} − {inter} = {a + b - inter}.",
        ]

    if "n" in params:
        n = params["n"]
        return [
            "Each element is independently in or out of a subset.",
            f"So |P(A)| = 2^{n} = {2**n}.",
        ]

    a, b = params["a"], params["b"]
    return [
        "The Cartesian product pairs every element of A with every element of B.",
        f"So |A × B| = |A|·|B| = {a}·{b} = {a * b}.",
    ]
