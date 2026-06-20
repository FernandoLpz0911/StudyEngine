"""Functional-dependency algorithms for CS 480 normalization problems.

Pure set logic — the single source of truth for both the generated answer and the
worked solution. An FD is a pair (lhs, rhs) of attribute frozensets; a schema is an
attribute frozenset plus a list of FDs.
"""
from __future__ import annotations

from itertools import combinations

FD = tuple[frozenset[str], frozenset[str]]


def closure(attrs: frozenset[str], fds: list[FD]) -> frozenset[str]:
    """Attribute closure X⁺: everything functionally determined by `attrs`."""
    result = set(attrs)
    changed = True
    while changed:
        changed = False
        for lhs, rhs in fds:
            if lhs <= result and not rhs <= result:
                result |= rhs
                changed = True
    return frozenset(result)


def is_superkey(attrs: frozenset[str], all_attrs: frozenset[str], fds: list[FD]) -> bool:
    """True when `attrs` determines every attribute in the relation."""
    return closure(attrs, fds) == all_attrs


def candidate_keys(all_attrs: frozenset[str], fds: list[FD]) -> list[frozenset[str]]:
    """All candidate keys: minimal attribute sets whose closure is the whole relation."""
    keys: list[frozenset[str]] = []
    attrs = sorted(all_attrs)
    for size in range(1, len(attrs) + 1):
        for combo in combinations(attrs, size):
            candidate = frozenset(combo)
            if any(key <= candidate for key in keys):
                continue  # superset of a smaller key — not minimal
            if is_superkey(candidate, all_attrs, fds):
                keys.append(candidate)
    return keys


def bcnf_violations(all_attrs: frozenset[str], fds: list[FD]) -> list[FD]:
    """FDs that violate BCNF: non-trivial with a left-hand side that is not a superkey."""
    return [
        (lhs, rhs)
        for lhs, rhs in fds
        if not rhs <= lhs and not is_superkey(lhs, all_attrs, fds)
    ]


def render_fds(fds: list[FD]) -> str:
    """Render FDs as 'A → B, AB → C' for problem statements."""
    parts = [f"{''.join(sorted(lhs))} → {''.join(sorted(rhs))}" for lhs, rhs in fds]
    return ", ".join(parts)
