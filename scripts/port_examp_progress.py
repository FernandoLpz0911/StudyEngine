"""Port Exam P progress from the LearningModel ancestor into this engine's `examp`.

LearningModel is the single-subject Exam P predecessor; its concept ids match the
`examp` ids here one-to-one, so its FSRS card states and interaction history can be
copied directly. Run once:

    python -m scripts.port_examp_progress

Idempotent-ish: it backs up the target DB first and skips concept ids that don't
exist locally. Re-running re-applies card_state (INSERT OR REPLACE) and appends a
fresh ported session of interactions, so run it only once unless you wipe examp.
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from engine.config import DB_PATH
from engine.db.seed import load_all

SUBJECT = "examp"
DEFAULT_SOURCE = Path("../LearningModel/data/app.db")


def port(source: Path, target: str) -> dict:
    if not source.exists():
        raise SystemExit(f"LearningModel DB not found: {source}")

    load_all()  # ensure schema + examp concepts exist locally (FK targets)
    backup = f"{target}.bak-{datetime.now(UTC):%Y%m%d%H%M%S}"
    shutil.copy(target, backup)

    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("ATTACH DATABASE ? AS src", (str(source),))

    local_ids = {
        r["id"]
        for r in conn.execute(
            "SELECT id FROM concept WHERE subject = ?", (SUBJECT,)
        )
    }

    cards = 0
    for r in conn.execute("SELECT * FROM src.card_state"):
        if r["concept_id"] not in local_ids:
            continue
        conn.execute(
            """INSERT OR REPLACE INTO card_state
               (concept_id, stability, difficulty, last_review, due,
                reps, lapses, step, state)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r["concept_id"], r["stability"], r["difficulty"], r["last_review"],
             r["due"], r["reps"], r["lapses"], r["step"], r["state"]),
        )
        cards += 1

    now = datetime.now(UTC).isoformat()
    sid = conn.execute(
        "INSERT INTO session (subject, started_at, ended_at) VALUES (?, ?, ?)",
        (SUBJECT, now, now),
    ).lastrowid

    inter = 0
    for r in conn.execute("SELECT * FROM src.interaction ORDER BY id"):
        if r["concept_id"] not in local_ids:
            continue
        conn.execute(
            """INSERT INTO interaction
               (session_id, concept_id, subject, kind, seed, params_json,
                correct_answer, user_answer, is_correct, grade, elapsed_ms,
                shown_at, answered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sid, r["concept_id"], SUBJECT, r["problem_kind"], r["seed"],
             r["params_json"], r["correct_answer"], r["user_answer"],
             r["is_correct"], r["grade"], r["elapsed_ms"], r["shown_at"],
             r["answered_at"]),
        )
        inter += 1

    conn.commit()
    conn.close()
    return {"backup": backup, "cards": cards, "interactions": inter}


def main() -> None:
    result = port(DEFAULT_SOURCE, DB_PATH)
    print(
        f"Ported {result['cards']} card states + {result['interactions']} "
        f"interactions into '{SUBJECT}'.\nBackup: {result['backup']}"
    )


if __name__ == "__main__":
    main()
