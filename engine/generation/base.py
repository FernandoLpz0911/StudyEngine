"""Problem-generation framework: dataclass, registry, and shared MC helpers.

Generators are registered under a ``kind`` string and take an explicit ``seed`` so
every problem is reproducible. The answer is computed in closed form, so the shown
solution and the graded answer cannot diverge.
"""
from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Problem:
    """A fully generated problem ready to serve."""

    kind: str
    ask: str
    statement: str
    correct_answer: float
    choices: list[str] | None  # None for free-response numeric
    tolerance: float = 1e-3
    params: dict = field(default_factory=dict)
    seed: int = 0


_generators: dict[str, Callable] = {}


def register(kind: str) -> Callable:
    """Decorator registering a generator function under `kind`."""
    def decorator(fn: Callable) -> Callable:
        _generators[kind] = fn
        return fn
    return decorator


def generate(kind: str, ask: str, params: dict, seed: int) -> Problem:
    """Dispatch to the generator registered for `kind`. Raises if none exists."""
    fn = _generators.get(kind)
    if fn is None:
        raise ValueError(f"No generator registered for kind '{kind}'")
    return fn(ask, params, seed)


def pick_ask(ask_list: list[str]) -> str:
    """Pick an ask type uniformly at random; the choice is logged via the kind."""
    return str(np.random.default_rng().choice(ask_list))


def make_mc_choices(
    correct: float,
    wrongs: list[float],
    rng: np.random.Generator,
    decimals: int = 3,
) -> list[str]:
    """Combine the correct answer with up to 3 distinct distractors into 4 shuffled choices."""
    def fmt(x: float) -> str:
        return f"{x:.{decimals}f}"

    target = fmt(correct)
    candidates: list[str] = []
    for w in wrongs:
        s = fmt(w)
        if s != target and s not in candidates:
            candidates.append(s)
        if len(candidates) == 3:
            break

    scale = max(abs(correct), 0.1)
    attempts = 0
    while len(candidates) < 3 and attempts < 200:
        perturbed = correct + rng.uniform(-0.6, 0.6) * scale
        s = fmt(perturbed)
        if s != target and s not in candidates:
            candidates.append(s)
        attempts += 1

    options = [target, *candidates[:3]]
    order = rng.permutation(len(options))
    return [options[i] for i in order]


def random_seed() -> int:
    return secrets.randbelow(2**31)
