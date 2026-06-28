"""Every concept must ship teachable theory so a beginner can learn it cold."""
import json
from pathlib import Path

import pytest

SEEDS = sorted(Path("data/subjects").glob("*/concept_graph.seed.json"))
MIN_CHARS = 120


def _concepts():
    for seed in SEEDS:
        data = json.loads(seed.read_text())
        for c in data["concepts"]:
            yield seed.parent.name, c


@pytest.mark.parametrize("subject,concept",
                         [(s, c) for s, c in _concepts()],
                         ids=[f"{s}:{c['id']}" for s, c in _concepts()])
def test_concept_has_theory(subject, concept):
    theory = (concept.get("theory_md") or "").strip()
    assert len(theory) >= MIN_CHARS, (
        f"{subject}/{concept['id']} has thin/missing theory_md "
        f"({len(theory)} chars)"
    )


def test_all_subjects_present():
    names = {s.parent.name for s in SEEDS}
    assert {"databases", "diffeq", "econ", "proofs", "examp", "examfm"} <= names
