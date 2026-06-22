"""Load subject concept-graph seed JSON into SQLite.

Each subject directory under SUBJECTS_DIR holds a concept_graph.seed.json with a
``subject`` key and a ``concepts`` list. A concept is one of two modes:

  - generator: has a ``generator`` object {kind, params}; problems are produced
    algorithmically with closed-form answers.
  - recall: has ``card`` {front, back}; a flashcard self-graded into FSRS.
"""
from __future__ import annotations

import json
from pathlib import Path

from engine.config import SUBJECTS_DIR
from engine.db.connection import get_connection, init_db


def load_subject(subject: str, seed_path: Path | None = None) -> int:
    """Insert/replace one subject's concepts. Returns the number of concepts loaded."""
    path = seed_path or Path(SUBJECTS_DIR) / subject / "concept_graph.seed.json"
    data = json.loads(path.read_text())
    concepts = data["concepts"]
    domain = data.get("domain")

    init_db()
    with get_connection() as conn:
        for c in concepts:
            generator = c.get("generator")
            card = c.get("card", {})
            mode = "generator" if generator else "recall"
            distractors = card.get("distractors")
            explanations = card.get("explanations")
            conn.execute(
                """
                INSERT OR REPLACE INTO concept
                    (id, subject, domain, name, category, mode, generator_json,
                     card_question, card_answer, card_distractors,
                     card_explanations, theory_md, exam_weight)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    c["id"],
                    subject,
                    c.get("domain", domain),
                    c["name"],
                    c.get("category"),
                    mode,
                    json.dumps(generator) if generator else None,
                    card.get("question"),
                    card.get("answer"),
                    json.dumps(distractors) if distractors else None,
                    json.dumps(explanations) if explanations else None,
                    c.get("theory_md"),
                    c.get("exam_weight", 1),
                ),
            )
            for prereq in c.get("prerequisites", []):
                conn.execute(
                    "INSERT OR IGNORE INTO concept_prereq (concept_id, prereq_id) VALUES (?, ?)",
                    (c["id"], prereq),
                )
    return len(concepts)


def load_all() -> dict[str, int]:
    """Load every subject directory found under SUBJECTS_DIR."""
    base = Path(SUBJECTS_DIR)
    loaded: dict[str, int] = {}
    for sub_dir in sorted(base.iterdir()):
        seed = sub_dir / "concept_graph.seed.json"
        if seed.exists():
            loaded[sub_dir.name] = load_subject(sub_dir.name, seed)
    return loaded
