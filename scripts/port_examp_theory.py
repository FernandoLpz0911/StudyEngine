"""Copy the rich Exam P teaching write-ups from LearningModel into `examp`.

The ancestor project ../LearningModel holds full markdown theory (## Why /
Intuition / Formulas / Worked Example / Key Properties / Exam Gotchas, with LaTeX
and tables) for the same 44 concept ids `examp` uses. This replaces examp's
one-line `theory_md` stubs with that content. Run once:

    python -m scripts.port_examp_theory

then re-seed (INSERT OR REPLACE updates concepts, keeps review history):

    python -c "from engine.db.seed import load_subject; load_subject('examp')"
"""
from __future__ import annotations

import json
from pathlib import Path

SEED = Path("data/subjects/examp/concept_graph.seed.json")
SOURCE = Path("../LearningModel/data/concept_theory.json")


def port() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"LearningModel theory not found: {SOURCE.resolve()}")
    theory: dict[str, str] = json.loads(SOURCE.read_text())
    data = json.loads(SEED.read_text())

    updated = 0
    for concept in data["concepts"]:
        rich = theory.get(concept["id"])
        if rich:
            concept["theory_md"] = rich
            updated += 1

    SEED.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return updated


if __name__ == "__main__":
    print(f"Updated theory_md for {port()} examp concepts.")
