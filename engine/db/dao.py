"""Data-access layer — all SQLite reads/writes go through here."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from engine.db.connection import get_connection


@dataclass
class Concept:
    """One node in a subject's concept graph."""

    id: str
    subject: str
    name: str
    category: str | None
    mode: str  # "generator" | "recall"
    generator: dict | None = None
    card_question: str | None = None
    card_answer: str | None = None
    card_distractors: list[str] = field(default_factory=list)
    theory_md: str | None = None
    exam_weight: int = 1
    prerequisites: list[str] = field(default_factory=list)


def _row_to_concept(row, prereqs: list[str]) -> Concept:
    return Concept(
        id=row["id"],
        subject=row["subject"],
        name=row["name"],
        category=row["category"],
        mode=row["mode"],
        generator=json.loads(row["generator_json"]) if row["generator_json"] else None,
        card_question=row["card_question"],
        card_answer=row["card_answer"],
        card_distractors=json.loads(row["card_distractors"]) if row["card_distractors"] else [],
        theory_md=row["theory_md"],
        exam_weight=row["exam_weight"],
        prerequisites=prereqs,
    )


def get_concepts(subject: str) -> list[Concept]:
    """All concepts for a subject, each with its prerequisite list."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM concept WHERE subject = ? ORDER BY id", (subject,)
        ).fetchall()
        prereq_rows = conn.execute("SELECT * FROM concept_prereq").fetchall()

    prereqs: dict[str, list[str]] = {}
    for row in prereq_rows:
        prereqs.setdefault(row["concept_id"], []).append(row["prereq_id"])

    return [_row_to_concept(row, prereqs.get(row["id"], [])) for row in rows]


def get_concept(concept_id: str) -> Concept | None:
    """A single concept with its prerequisites, or None if not found."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM concept WHERE id = ?", (concept_id,)).fetchone()
        if row is None:
            return None
        prereq_rows = conn.execute(
            "SELECT prereq_id FROM concept_prereq WHERE concept_id = ?", (concept_id,)
        ).fetchall()
    return _row_to_concept(row, [r["prereq_id"] for r in prereq_rows])


def list_subjects() -> list[str]:
    """Distinct subjects present in the database."""
    with get_connection() as conn:
        rows = conn.execute("SELECT DISTINCT subject FROM concept ORDER BY subject").fetchall()
    return [r["subject"] for r in rows]


def create_session(subject: str) -> int:
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO session (subject, started_at) VALUES (?, ?)", (subject, now)
        )
        return cur.lastrowid


def close_session(session_id: int) -> None:
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute("UPDATE session SET ended_at = ? WHERE id = ?", (now, session_id))


def log_shown(
    session_id: int,
    concept_id: str,
    subject: str,
    kind: str,
    seed: int = 0,
    params_json: str = "{}",
    correct_answer: str | None = None,
) -> int:
    """Record that a problem/card was served. Returns the interaction id."""
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO interaction
                (session_id, concept_id, subject, kind, seed, params_json,
                 correct_answer, shown_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, concept_id, subject, kind, seed, params_json, correct_answer, now),
        )
        return cur.lastrowid


def log_answered(
    item_id: int,
    user_answer: str | None,
    is_correct: bool | None,
    grade: int,
    elapsed_ms: int = 0,
) -> None:
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE interaction
            SET user_answer = ?, is_correct = ?, grade = ?,
                elapsed_ms = ?, answered_at = ?
            WHERE id = ?
            """,
            (
                user_answer,
                int(is_correct) if is_correct is not None else None,
                grade,
                elapsed_ms,
                now,
                item_id,
            ),
        )


def get_concept_accuracy(concept_id: str, window: int = 10) -> float | None:
    """Recent fraction-correct for a concept over its last `window` graded items."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT is_correct FROM interaction
            WHERE concept_id = ? AND is_correct IS NOT NULL
            ORDER BY id DESC LIMIT ?
            """,
            (concept_id, window),
        ).fetchall()
    if not rows:
        return None
    return sum(r["is_correct"] for r in rows) / len(rows)


def subject_stats(subject: str) -> dict:
    """Answered count and accuracy for a subject (for the study summary)."""
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM interaction WHERE subject = ? AND is_correct IS NOT NULL",
            (subject,),
        ).fetchone()["n"]
        correct = conn.execute(
            "SELECT COUNT(*) AS n FROM interaction WHERE subject = ? AND is_correct = 1",
            (subject,),
        ).fetchone()["n"]
    return {
        "answered": total,
        "correct": correct,
        "accuracy": round(correct / total, 3) if total else 0.0,
    }


def all_concept_ids() -> list[str]:
    """Every concept id across all subjects, sorted (the global DKT index order)."""
    with get_connection() as conn:
        rows = conn.execute("SELECT id FROM concept ORDER BY id").fetchall()
    return [r["id"] for r in rows]


def count_answered_interactions() -> int:
    """Total graded interactions across all subjects (for the DKT activation gate)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM interaction WHERE is_correct IS NOT NULL"
        ).fetchone()
    return row["n"] if row else 0


def get_interaction_history_timed(
    limit: int = 1000,
) -> list[tuple[str, bool, float]]:
    """Recent (concept_id, is_correct, time_days) across all subjects, oldest first.

    time_days is shown_at as days-since-epoch (falls back to sequence position),
    feeding the DKT model's recall-lag features. The interleaved global history is
    exactly the cross-domain sequence the model trains and predicts on.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT concept_id, is_correct, shown_at FROM interaction
            WHERE is_correct IS NOT NULL
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    history: list[tuple[str, bool, float]] = []
    for position, row in enumerate(reversed(rows)):
        try:
            t = datetime.fromisoformat(row["shown_at"]).timestamp() / 86400.0
        except (ValueError, TypeError):
            t = float(position)
        history.append((row["concept_id"], bool(row["is_correct"]), t))
    return history
