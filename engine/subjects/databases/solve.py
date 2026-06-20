"""Worked solutions for CS 480 normalization problems (shares the FD engine)."""
from __future__ import annotations

from engine.feedback.solve import register_solver
from engine.subjects.databases import fd

ALL_ATTRS = frozenset("ABCD")


def _parse_fds(params: dict) -> list[fd.FD]:
    return [(frozenset(lhs), frozenset(rhs)) for lhs, rhs in params["fds"]]


def _braced(attrs: frozenset[str]) -> str:
    return "{" + "".join(sorted(attrs)) + "}"


@register_solver("fd_closure")
@register_solver("candidate_keys")
@register_solver("bcnf_check")
def worked_steps(kind: str, ask: str, params: dict) -> list[str]:
    fds = _parse_fds(params)

    if kind == "fd_closure":
        x = frozenset(params["x"])
        result = fd.closure(x, fds)
        return [
            f"Start from {_braced(x)} and apply the FDs {fd.render_fds(fds)} until "
            f"nothing new is added.",
            f"Closure {_braced(x)}⁺ = {_braced(result)}.",
            f"It contains {len(result)} attribute(s).",
        ]

    if kind == "candidate_keys":
        keys = fd.candidate_keys(ALL_ATTRS, fds)
        listed = ", ".join(_braced(k) for k in keys) or "none"
        return [
            "A candidate key is a minimal attribute set whose closure is all of R.",
            f"Minimal keys: {listed}.",
            f"So R has {len(keys)} candidate key(s).",
        ]

    violations = fd.bcnf_violations(ALL_ATTRS, fds)
    listed = fd.render_fds(violations) if violations else "none"
    tail = " R is in BCNF." if not violations else ""
    return [
        "An FD X → Y violates BCNF when it is non-trivial and X is not a superkey.",
        f"Violating FDs: {listed}.",
        f"Violation count = {len(violations)}.{tail}",
    ]
