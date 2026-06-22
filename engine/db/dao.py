"""Data-access layer — all SQLite reads/writes go through here."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from engine.db.connection import get_connection


@dataclass
class Concept:
    """One node in a subject's concept graph."""

    id: str
    subject: str
    name: str
    category: str | None
    mode: str  # "generator" | "recall"
    domain: str | None = None
    generator: dict | None = None
    card_question: str | None = None
    card_answer: str | None = None
    card_distractors: list[str] = field(default_factory=list)
    card_explanations: dict[str, str] = field(default_factory=dict)
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
        domain=row["domain"] if "domain" in row.keys() else None,
        generator=json.loads(row["generator_json"]) if row["generator_json"] else None,
        card_question=row["card_question"],
        card_answer=row["card_answer"],
        card_distractors=json.loads(row["card_distractors"]) if row["card_distractors"] else [],
        card_explanations=(
            json.loads(row["card_explanations"])
            if "card_explanations" in row.keys() and row["card_explanations"]
            else {}
        ),
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


def save_mnemonic(concept_id: str, text: str) -> None:
    """Store the learner's own hint for a concept (IKEA effect: they invest)."""
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO mnemonic (concept_id, text, created_at) "
            "VALUES (?, ?, ?)",
            (concept_id, text, now),
        )


def get_mnemonic(concept_id: str) -> str | None:
    """The learner's saved hint for a concept, resurfaced on later encounters."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT text FROM mnemonic WHERE concept_id = ?", (concept_id,)
        ).fetchone()
    return row["text"] if row else None


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


def total_xp() -> int:
    """Lifetime XP: every correct retrieval scores its FSRS grade × exam weight.

    Ties progression to *spaced retrieval value*, not time-on-app — a fast, hard,
    high-weight concept recalled correctly is worth more than an easy repeat, and a
    wrong answer scores nothing. Keeps the addictive number aligned with learning.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(i.grade * COALESCE(c.exam_weight, 1)), 0) AS xp
            FROM interaction i JOIN concept c ON c.id = i.concept_id
            WHERE i.is_correct = 1
            """
        ).fetchone()
    return int(row["xp"]) if row else 0


def _answered_days() -> list[date]:
    """Distinct UTC dates on which any item was answered, most recent first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT date(answered_at, ?) AS d FROM interaction "
            "WHERE answered_at IS NOT NULL ORDER BY d DESC",
            (_tz_modifier(),),
        ).fetchall()
    out: list[date] = []
    for row in rows:
        try:
            out.append(date.fromisoformat(row["d"]))
        except (ValueError, TypeError):
            continue
    return out


def _tz_modifier() -> str:
    """SQLite datetime modifier shifting UTC to the configured local day boundary."""
    from engine.config import STREAK_TZ_OFFSET
    return f"{STREAK_TZ_OFFSET:+g} hours"


def _local_today() -> date:
    from engine.config import STREAK_TZ_OFFSET
    return (datetime.now(UTC) + timedelta(hours=STREAK_TZ_OFFSET)).date()


def daily_streak(today: date | None = None) -> int:
    """Consecutive study days ending today, with earned freezes bridging slips.

    Loss aversion: a visible streak the learner won't want to break is the single
    strongest pull back into the app, and it enforces the daily cadence FSRS needs.
    One freeze is earned per STREAK_FREEZE_EARN_DAYS studied days; each silently
    bridges a single missed day so one slip never resets the chain.
    """
    from engine.config import STREAK_FREEZE_EARN_DAYS
    today = today or _local_today()
    days = set(_answered_days())
    if not days:
        return 0
    bridges = len(days) // STREAK_FREEZE_EARN_DAYS
    cursor = today
    if cursor not in days:  # current day still in progress — don't penalise it
        cursor -= timedelta(days=1)
    streak = 0
    while True:
        if cursor in days:
            streak += 1
        elif bridges > 0:
            bridges -= 1  # a freeze covers this gap; chain survives
        else:
            break
        cursor -= timedelta(days=1)
    return streak


def freeze_status() -> dict:
    """Earned / consumed streak freezes — surfaced so the safety net is visible."""
    from engine.config import STREAK_FREEZE_EARN_DAYS
    earned = len(_answered_days()) // STREAK_FREEZE_EARN_DAYS
    return {"earned": earned, "earn_days": STREAK_FREEZE_EARN_DAYS}


def study_days(limit: int = 372) -> list[str]:
    """Recent distinct local study dates (ISO) for the contribution heatmap."""
    return [d.isoformat() for d in _answered_days()[:limit]]


def count_answered_today(today: date | None = None) -> int:
    """Items answered so far on the current local day (drives the daily-goal ring)."""
    today = (today or _local_today()).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM interaction "
            "WHERE answered_at IS NOT NULL AND date(answered_at, ?) = ?",
            (_tz_modifier(), today),
        ).fetchone()
    return row["n"] if row else 0


def leeches() -> list[dict]:
    """Concepts repeatedly forgotten (lapses ≥ LEECH_LAPSES) — the costly few."""
    from engine.config import LEECH_LAPSES
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT cs.concept_id AS id, c.name AS name, c.subject AS subject, "
            "cs.lapses AS lapses FROM card_state cs JOIN concept c ON c.id = cs.concept_id "
            "WHERE cs.lapses >= ? ORDER BY cs.lapses DESC",
            (LEECH_LAPSES,),
        ).fetchall()
    return [dict(r) for r in rows]


def personal_bests() -> dict:
    """Fastest correct answer, best single day, and longest-ever correct run."""
    with get_connection() as conn:
        fastest = conn.execute(
            "SELECT MIN(elapsed_ms) AS ms FROM interaction "
            "WHERE is_correct = 1 AND elapsed_ms > 0"
        ).fetchone()["ms"]
        best_day = conn.execute(
            "SELECT MAX(n) AS m FROM (SELECT COUNT(*) AS n FROM interaction "
            "WHERE answered_at IS NOT NULL GROUP BY date(answered_at, ?))",
            (_tz_modifier(),),
        ).fetchone()["m"]
        seq = conn.execute(
            "SELECT is_correct FROM interaction WHERE is_correct IS NOT NULL ORDER BY id"
        ).fetchall()
    run = best = 0
    for r in seq:
        run = run + 1 if r["is_correct"] else 0
        best = max(best, run)
    return {
        "fastest_ms": fastest,
        "best_day": best_day or 0,
        "longest_run": best,
    }


def due_count() -> int:
    """Concepts whose FSRS review is due now (the 'reviews waiting' open loop)."""
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM card_state "
            "WHERE reps > 0 AND due IS NOT NULL AND due <= ?",
            (now,),
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
