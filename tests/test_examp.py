"""Port sanity for Exam P: every generator's answer is in its choices and has a
worked solution, across many seeds. Drives directly off the seeded concept graph.
"""
import json
from pathlib import Path

import pytest

import engine.subjects  # noqa: F401  (registers Exam P generators + solvers)
from engine.feedback.solve import worked_solution
from engine.generation.base import generate

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
