"""Port sanity for Exam P: every generator's answer is in its choices and has a
worked solution, across many seeds. Drives directly off the seeded concept graph.
"""
import json
import re
from pathlib import Path

import pytest

import engine.subjects  # noqa: F401  (registers Exam P generators + solvers)
from engine.feedback.solve import worked_solution
from engine.generation.base import generate
from engine.subjects.examp.solve import solve as _solved

GRAPH = json.loads(
    Path("data/subjects/examp/concept_graph.seed.json").read_text()
)
CASES = [
    (c["generator"]["kind"], ask, c["generator"]["params"])
    for c in GRAPH["concepts"]
    for ask in c["generator"]["params"]["ask"]
]


def test_all_concepts_are_generators():
    assert len(GRAPH["concepts"]) == 44
    assert all("generator" in c for c in GRAPH["concepts"])


@pytest.mark.parametrize("kind,ask,params", CASES)
def test_answer_in_choices_and_has_worked_solution(kind, ask, params):
    for seed in range(12):
        problem = generate(kind, ask, params, seed)
        if problem.choices is not None:
            assert f"{problem.correct_answer:.3f}" in problem.choices
        assert worked_solution(kind, ask, problem.params)


# Naming the tool, or restating its closed form on the right of the ask. Bare
# equations are fine — "Find P(X = 3)" states the question, "Find Var(X) =
# E[X²] − (E[X])²" answers it — so only a right-hand side that opens into symbols
# counts as a leak.
LEAKS = re.compile(
    r"\busing\b|\bvia\b|\brecall\b|\bverify\b|note that|\bhint\b|\bformula\b"
    r"|\bi\.e\.\b|\bstandardize\b|\bmemoryless\b|\btower\b|law of total"
    r"|change-of-variables|CDF method|\bBayes\b|Chebyshev|Markov|\bCLT\b"
    r"|triangular|=\s*(E\[|Var\(|Cov\(|S\(|M'|C\(|P\(\d|θ/|1 - \[|αθ)",
    re.I,
)


@pytest.mark.parametrize("kind,ask,params", CASES)
def test_statement_gives_no_method_away(kind, ask, params):
    """A question states the situation and what to find — never how to find it.

    Naming the tool ("using the law of total variance"), restating the closed form
    inside the ask ("Find E[X²] = Var(X) + (E[X])²"), or supplying an intermediate
    the learner should derive turns a problem into arithmetic. The real sitting
    supplies none of it.
    """
    for seed in range(6):
        statement = generate(kind, ask, params, seed).statement
        found = LEAKS.search(statement)
        assert not found, f"{kind}:{ask} hands over '{found.group()}' — {statement}"


@pytest.mark.parametrize("kind,ask,params", CASES)
def test_solver_answer_matches_the_graded_key(kind, ask, params):
    """The worked solution must reach the same number the answer is graded against.

    Exam P still splits generation from its explanation across `solve.py` (the
    legacy path being retired, ADR-0003), so the two can silently disagree — the
    learner is marked wrong and then shown a solution ending in a different value.
    Nothing else pins them together: the sibling test only checks that a solution
    exists and that the key is among the choices.
    """
    for seed in range(12):
        problem = generate(kind, ask, params, seed)
        solved = _solved(kind, ask, problem.params)
        assert solved.answer == pytest.approx(problem.correct_answer, rel=1e-3, abs=1e-3), (
            f"{kind}:{ask} seed={seed} — solver says {solved.answer}, "
            f"key is {problem.correct_answer}"
        )
