"""CS 480 normalization generators — closed-form answers from the FD engine.

Each problem builds a small random schema R(A,B,C,D) with functional dependencies,
then asks a question whose numeric answer is computed by engine.subjects.databases.fd
(the same code the worked solution uses).
"""
from __future__ import annotations

import numpy as np

from engine.generation.base import Problem, make_int_choices, register
from engine.subjects.databases import fd

ATTRS = ["A", "B", "C", "D"]


def _random_schema(rng: np.random.Generator) -> tuple[frozenset[str], list[fd.FD]]:
    all_attrs = frozenset(ATTRS)
    n_fds = int(rng.integers(2, 4))
    fds: list[fd.FD] = []
    seen: set[tuple] = set()
    guard = 0
    while len(fds) < n_fds and guard < 100:
        guard += 1
        lhs_size = 1 if rng.random() < 0.7 else 2
        lhs = frozenset(str(a) for a in rng.choice(ATTRS, size=lhs_size, replace=False))
        rhs_pool = [a for a in ATTRS if a not in lhs]
        rhs = frozenset([str(rng.choice(rhs_pool))])
        key = (lhs, rhs)
        if key in seen:
            continue
        seen.add(key)
        fds.append((lhs, rhs))
    return all_attrs, fds


def _fds_param(fds: list[fd.FD]) -> list[list[list[str]]]:
    return [[sorted(lhs), sorted(rhs)] for lhs, rhs in fds]


@register("fd_closure")
def gen_fd_closure(ask: str, params: dict, seed: int) -> Problem:
    """Compute the size of an attribute closure X⁺."""
    rng = np.random.default_rng(seed)
    all_attrs, fds = _random_schema(rng)
    x_size = int(rng.integers(1, 3))
    x = frozenset(str(a) for a in rng.choice(ATTRS, size=x_size, replace=False))

    answer = len(fd.closure(x, fds))
    x_str = "".join(sorted(x))
    statement = (
        f"Relation R(A, B, C, D) with functional dependencies: {fd.render_fds(fds)}. "
        f"How many attributes are in the closure {{{x_str}}}⁺?"
    )
    return Problem(
        "fd_closure", "closure_size", statement, float(answer),
        make_int_choices(answer, rng, lo=len(x), hi=4),
        params={"fds": _fds_param(fds), "x": sorted(x)}, seed=seed,
    )


@register("candidate_keys")
def gen_candidate_keys(ask: str, params: dict, seed: int) -> Problem:
    """Count the candidate keys of a schema."""
    rng = np.random.default_rng(seed)
    all_attrs, fds = _random_schema(rng)
    answer = len(fd.candidate_keys(all_attrs, fds))
    statement = (
        f"Relation R(A, B, C, D) with functional dependencies: {fd.render_fds(fds)}. "
        f"How many candidate keys does R have?"
    )
    return Problem(
        "candidate_keys", "count", statement, float(answer),
        make_int_choices(answer, rng, lo=1, hi=4),
        params={"fds": _fds_param(fds)}, seed=seed,
    )


@register("bcnf_check")
def gen_bcnf_check(ask: str, params: dict, seed: int) -> Problem:
    """Count the FDs that violate BCNF (non-trivial, left side not a superkey)."""
    rng = np.random.default_rng(seed)
    all_attrs, fds = _random_schema(rng)
    answer = len(fd.bcnf_violations(all_attrs, fds))
    statement = (
        f"Relation R(A, B, C, D) with functional dependencies: {fd.render_fds(fds)}. "
        f"How many of these FDs violate BCNF (a non-trivial FD whose left-hand "
        f"side is not a superkey)? (0 means R is in BCNF.)"
    )
    return Problem(
        "bcnf_check", "violation_count", statement, float(answer),
        make_int_choices(answer, rng, lo=0, hi=len(fds)),
        params={"fds": _fds_param(fds)}, seed=seed,
    )
