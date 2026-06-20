"""Registry mapping a generator `kind` to its worked-solution step list.

Each generator subject registers a solver under the kinds it produces, so the CLI
can show a deterministic worked solution for any subject without knowing which one
it came from.
"""
from __future__ import annotations

from collections.abc import Callable

Solver = Callable[[str, str, dict], list[str]]
_solvers: dict[str, Solver] = {}


def register_solver(kind: str) -> Callable[[Solver], Solver]:
    """Decorator registering a solver `fn(kind, ask, params) -> steps` for `kind`."""
    def decorator(fn: Solver) -> Solver:
        _solvers[kind] = fn
        return fn
    return decorator


def worked_solution(kind: str, ask: str, params: dict) -> list[str]:
    """Return the worked-solution steps for a problem, or [] if none is registered."""
    fn = _solvers.get(kind)
    return fn(kind, ask, params) if fn else []
