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
    """A fully generated problem ready to serve.

    `explain` is the worked solution, produced by the generator from the same
    closed-form computation as `correct_answer` so the two cannot diverge. A
    generator that hasn't been migrated leaves it empty; `service.build_item`
    then falls back to the legacy `feedback.solve` registry.
    """

    kind: str
    ask: str
    statement: str
    correct_answer: float
    choices: list[str] | None  # None for free-response numeric
    tolerance: float = 1e-3
    params: dict = field(default_factory=dict)
    seed: int = 0
    explain: list[str] = field(default_factory=list)


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


def make_int_choices(
    correct: int,
    rng: np.random.Generator,
    lo: int = 0,
    hi: int = 8,
    prefer: tuple[int, ...] = (),
) -> list[str]:
    """Four distinct integer options (including `correct`), formatted like the answer.

    `prefer` lists pedagogically chosen distractors (common wrong counts) tried
    first; any remaining slots are padded with random integers in [lo, hi]. Used
    for count-style questions where non-integer distractors would look wrong.
    """
    options = [correct]
    for wrong in prefer:
        if wrong not in options and len(options) < 4:
            options.append(wrong)
    guard = 0
    while len(options) < 4 and guard < 300:
        guard += 1
        candidate = int(rng.integers(lo, hi + 1))
        if candidate not in options:
            options.append(candidate)
    rng.shuffle(options)
    return [f"{value:.3f}" for value in options]


def random_seed() -> int:
    return secrets.randbelow(2**31)
